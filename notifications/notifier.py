# backend/visitors/views/notifications.py
from rest_framework import views, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.viewsets import GenericViewSet
import pusher
from django.conf import settings
from django.utils import timezone
import logging
from django.core.mail import send_mail
import requests
from visitors.models import Visitor, CustomUser, VisitorLog
from visitors.serializers import VisitorSerializer
from visitors.permissions import IsAdminUser, IsReceptionistUser
from asgiref.sync import async_to_sync
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from visitors.models import Notification
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)

# ========== PUSHER CONFIGURATION ==========
PUSHER_APP_ID = getattr(settings, "PUSHER_APP_ID", "2022219")
PUSHER_KEY = getattr(settings, "PUSHER_KEY", "6fdb9e38bb8d77e577c3")
PUSHER_SECRET = getattr(settings, "PUSHER_SECRET", "4f32f1729df7270251a8")
PUSHER_CLUSTER = getattr(settings, "PUSHER_CLUSTER", "mt1")

pusher_client = pusher.Pusher(
    app_id=PUSHER_APP_ID,
    key=PUSHER_KEY,
    secret=PUSHER_SECRET,
    cluster=PUSHER_CLUSTER,
    ssl=True
)

# ========== NOTIFICATION UTILITY FUNCTIONS ==========
def send_email_notification(subject, message, recipient_list):
    """Send email notification to one or more recipients"""
    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            recipient_list,
            fail_silently=False
        )
        logger.info(f"Email sent to {recipient_list}")
        return True
    except Exception as e:
        logger.error(f"Email Error: {e}")
        return False

def send_sms_notification(phone, message):
    """Send SMS notification via Pusher"""
    try:
        pusher_client.trigger('sms_channel', 'new_sms', {
            'to': phone,
            'message': message
        })
        logger.info(f"SMS sent to {phone} via Pusher")
        return True
    except Exception as e:
        logger.error(f"Pusher SMS error: {e}")
        return False

def send_whatsapp_notification(to, message):
    """Send WhatsApp notification via Facebook Graph API"""
    url = f"https://graph.facebook.com/v18.0/{settings.WHATSAPP_PHONE_ID}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": message}
    }
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            logger.info(f"WhatsApp message sent to {to}")
            return response.json()
        logger.error(f"WhatsApp API error: {response.status_code} - {response.text}")
        return False
    except Exception as e:
        logger.error(f"WhatsApp API error: {e}")
        return False

def trigger_pusher_notification(channels, event, data):
    """
    Triggers a real-time notification using Pusher.
    Can handle single channel or list of channels.
    """
    if not isinstance(channels, list):
        channels = [channels]
    
    try:
        for channel in channels:
            pusher_client.trigger(channel, event, data)
            logger.info(f"Pusher event '{event}' sent on channel '{channel}'")
        return True
    except Exception as e:
        logger.error(f"Pusher notification error: {e}")
        return False

def trigger_host_notification(host, message):
    """
    Triggers email, SMS, and WhatsApp notifications to a host.
    'host' is expected to be an object with email, phone, and whatsapp_number attributes.
    """
    results = {
        'email': False,
        'sms': False,
        'whatsapp': False
    }

    subject = "Visitor Alert Notification"

    if hasattr(host, 'email') and host.email:
        results['email'] = send_email_notification(subject, message, [host.email])

    if hasattr(host, 'phone') and host.phone:
        results['sms'] = send_sms_notification(host.phone, message)

    if hasattr(host, 'whatsapp_number') and host.whatsapp_number:
        results['whatsapp'] = send_whatsapp_notification(host.whatsapp_number, message)

    return results

def send_notification(visitor=None, host=None, message="", channels=['email'], subject="Notification"):
    results = {}

    def save_notification(recipient, channel):
        if recipient:
            Notification.objects.create(
                recipient=recipient,
                channel=channel,
                message=message
            )

    if 'email' in channels:
        recipients = []
        if visitor and visitor.email:
            recipients.append(visitor.email)
        if host and host.email:
            recipients.append(host.email)
        if recipients:
            results['email'] = send_email_notification(subject, message, recipients)
            for r in recipients:
                save_notification(r, 'email')

    if 'sms' in channels:
        recipients = []
        if visitor and visitor.phone:
            recipients.append(visitor.phone)
        if host and host.phone:
            recipients.append(host.phone)
        if recipients:
            results['sms'] = all(send_sms_notification(phone, message) for phone in recipients)
            for r in recipients:
                save_notification(r, 'sms')

    if 'whatsapp' in channels:
        recipients = []
        if visitor and visitor.phone:
            recipients.append(visitor.phone)
        if host and host.phone:
            recipients.append(host.phone)
        if recipients:
            results['whatsapp'] = all(send_whatsapp_notification(phone, message) for phone in recipients)
            for r in recipients:
                save_notification(r, 'whatsapp')

    if 'pusher' in channels:
        data = {
            "message": message,
            "timestamp": timezone.now().isoformat(),
            "visitor": VisitorSerializer(visitor).data if visitor else None
        }
        pusher_channels = []
        if host:
            pusher_channels.append(f"private-user-{host.id}")
        if visitor:
            pusher_channels.append("private-reception-channel")
        if pusher_channels:
            results['pusher'] = trigger_pusher_notification(pusher_channels, "visitor-notification", data)
            for r in pusher_channels:
                save_notification(r, 'pusher')

    return results

def send_realtime_notification(user, message, event=None, data=None, channel='general', status='sent'):
    """
    Sends a real-time notification over WebSocket.
    If `channel` is provided, it overrides user-based group.
    """
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync

    channel_layer = get_channel_layer()
    group_name = channel or (f"user_{user.id}" if user else None)

    if not group_name:
        raise ValueError("Either `user` or `channel` must be provided.")

    payload = {
        "type": "send_notification",
        "message": message,
        "event": event,
        "data": data,
    }

    async_to_sync(channel_layer.group_send)(group_name, payload)

# ========== NOTIFICATION VIEWS ==========
class NotificationViewSet(GenericViewSet):
    """
    API endpoints for managing all notification types.
    Handles visitor notifications, manual alerts, preferences, and bulk notifications.
    """
    permission_classes = [IsAuthenticated]
    queryset = Visitor.objects.none()  # Required for ViewSet but not used directly

    def get_permissions(self):
        if self.action in ['bulk_notify', 'system_alert']:
            return [IsAuthenticated(), IsAdminUser()]
        elif self.action in ['manual_notify', 'host_notify']:
            return [IsAuthenticated(), IsReceptionistUser()]
        return super().get_permissions()

    @action(detail=False, methods=['post'])
    def notify_visitor(self, request):
        """
        Send notifications to visitors and/or hosts via multiple channels.
        Supports email, SMS, WhatsApp, and Pusher real-time notifications.
        """
        data = request.data
        visitor_id = data.get('visitor_id')
        host_id = data.get('host_id')
        message = data.get('message', '')
        subject = data.get('subject', 'Notification')
        channels = data.get('channels', ['email'])

        # Validate input
        if not visitor_id and not host_id:
            return Response(
                {"error": "Either visitor_id or host_id must be provided"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            visitor = Visitor.objects.get(id=visitor_id) if visitor_id else None
            host = CustomUser.objects.get(id=host_id) if host_id else None
        except (Visitor.DoesNotExist, CustomUser.DoesNotExist) as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_404_NOT_FOUND
            )

        results = {}
        for channel in channels:
            try:
                if channel == 'email':
                    results['email'] = self._send_email(
                        visitor, host, subject, message
                    )
                elif channel == 'sms':
                    results['sms'] = self._send_sms(
                        visitor, host, message
                    )
                elif channel == 'whatsapp':
                    results['whatsapp'] = self._send_whatsapp(
                        visitor, host, message
                    )
                elif channel == 'pusher':
                    results['pusher'] = self._send_pusher(
                        visitor, host, message
                    )
            except Exception as e:
                logger.error(f"Error sending {channel} notification: {str(e)}")
                results[channel] = {"status": "failed", "error": str(e)}

        # Log the notification event
        if visitor:
            VisitorLog.objects.create(
                visitor=visitor,
                action='NOTIFICATION_SENT',
                details=f"Notification via {', '.join(channels)}: {message}",
                user=request.user
            )

        return Response({
            "status": "Notifications processed",
            "results": results,
            "timestamp": timezone.now().isoformat()
        })

    @action(detail=False, methods=['post'])
    def manual_notify(self, request):
        """
        Send custom manual notifications to specific channels.
        Used by receptionists for ad-hoc communications.
        """
        channel = request.data.get('channel')
        event = request.data.get('event')
        data = request.data.get('data', {})
        broadcast = request.data.get('broadcast', False)

        if not channel or not event:
            return Response(
                {"error": "Channel and event parameters are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Enhance notification data
            enhanced_data = {
                **data,
                "sent_by": request.user.email,
                "timestamp": timezone.now().isoformat()
            }

            if broadcast:
                trigger_pusher_notification([channel], event, enhanced_data)
            else:
                trigger_pusher_notification(channel, event, enhanced_data)

            # Log the manual notification
            VisitorLog.objects.create(
                action='MANUAL_NOTIFICATION',
                details=f"Manual notification to {channel}: {data.get('message')}",
                user=request.user
            )

            return Response({
                "status": "Notification sent",
                "channel": channel,
                "event": event
            })
        except Exception as e:
            logger.error(f"Manual notification failed: {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'])
    def bulk_notify(self, request):
        """
        Send bulk notifications to multiple users (Admin only).
        Supports email and Pusher channels.
        """
        user_ids = request.data.get('user_ids', [])
        message = request.data.get('message')
        channels = request.data.get('channels', ['email'])
        data = request.data.get('data', {})

        if not user_ids or not message:
            return Response(
                {"error": "user_ids and message are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            users = CustomUser.objects.filter(id__in=user_ids)
            results = []

            for user in users:
                result = {"user_id": user.id, "email": user.email}
                
                if 'email' in channels and user.email:
                    try:
                        send_email_notification(
                            subject=data.get('subject', 'Notification'),
                            message=message,
                            recipient_list=[user.email]
                        )
                        result['email'] = "sent"
                    except Exception as e:
                        result['email'] = str(e)

                if 'pusher' in channels:
                    try:
                        trigger_pusher_notification(
                            f"private-user-{user.id}",
                            "bulk-notification",
                            {
                                "message": message,
                                "data": data,
                                "timestamp": timezone.now().isoformat()
                            }
                        )
                        result['pusher'] = "sent"
                    except Exception as e:
                        result['pusher'] = str(e)

                results.append(result)

            # Log bulk notification
            VisitorLog.objects.create(
                action='BULK_NOTIFICATION',
                details=f"Bulk notification to {len(users)} users",
                user=request.user
            )

            return Response({
                "status": "Bulk notifications processed",
                "total_sent": len([r for r in results if any(v == "sent" for v in r.values())]),
                "results": results
            })
        except Exception as e:
            logger.error(f"Bulk notification failed: {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get', 'put'])
    def preferences(self, request):
        """
        Get or update user notification preferences.
        """
        if request.method == 'GET':
            return Response(request.user.notification_preferences)
        
        request.user.notification_preferences = {
            **request.user.notification_preferences,
            **request.data
        }
        request.user.save()
        return Response({"status": "Preferences updated"})

    def _send_email(self, visitor, host, subject, message):
        """Send email notification"""
        recipients = []
        if visitor and visitor.email:
            recipients.append(visitor.email)
        if host and host.email:
            recipients.append(host.email)

        if not recipients:
            return {"status": "skipped", "reason": "No valid email recipients"}

        send_email_notification(subject, message, recipients)
        return {"status": "success", "recipients": recipients}

    def _send_sms(self, visitor, host, message):
        """Send SMS notification"""
        recipients = []
        if visitor and visitor.phone:
            recipients.append(visitor.phone)
        if host and host.phone:
            recipients.append(host.phone)

        if not recipients:
            return {"status": "skipped", "reason": "No valid phone numbers"}

        results = [send_sms_notification(phone, message) for phone in recipients]
        return {"status": "success", "results": results}

    def _send_whatsapp(self, visitor, host, message):
        """Send WhatsApp notification"""
        recipients = []
        if visitor and visitor.phone:
            recipients.append(visitor.phone)
        if host and host.phone:
            recipients.append(host.phone)

        if not recipients:
            return {"status": "skipped", "reason": "No valid phone numbers"}

        results = [send_whatsapp_notification(phone, message) for phone in recipients]
        return {"status": "success", "results": results}

    def _send_pusher(self, visitor, host, message):
        """Send real-time Pusher notification"""
        data = {
            "message": message,
            "timestamp": timezone.now().isoformat(),
            "visitor": VisitorSerializer(visitor).data if visitor else None
        }

        channels = []
        if host:
            channels.append(f"private-user-{host.id}")
        if visitor:
            channels.append("private-reception-channel")

        trigger_pusher_notification(channels, "visitor-notification", data)
        return {"status": "success", "channels": channels}

class ManualNotificationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        message = request.data.get('message')
        trigger_pusher_notification('admin_channel', 'manual_alert', message or "No message")
        return Response({"status": "Notification sent"}, status=200)

    
class NotifyVisitorView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]

    def post(self, request):
        visitor_name = request.data.get('name')
        contact = request.data.get('contact')
        message = request.data.get('message')

        # Here you would integrate with Twilio, Africa's Talking, etc.
        print(f"Sending notification to {visitor_name} ({contact}): {message}")
        
        return Response({"detail": f"Notification sent to {visitor_name}."}, status=status.HTTP_200_OK)


class SubscribeToNotificationsView(APIView):
    def post(self, request):
        email = request.data.get("email")
        # Logic to store the subscription (e.g., save to DB)
        print(f"Subscribed {email} to notifications.")
        return Response({"detail": f"Subscribed {email}."}, status=status.HTTP_201_CREATED)


class NotificationPreferencesView(APIView):
    def post(self, request):
        user_id = request.data.get("user_id")
        preferences = request.data.get("preferences")  # e.g. {"email": True, "sms": False}
        
        # Save preferences to DB (this is mocked here)
        print(f"Saved preferences for user {user_id}: {preferences}")
        return Response({"detail": "Preferences updated."}, status=status.HTTP_200_OK)

class NotificationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        notifications = Notification.objects.filter(recipient=request.user.email).order_by('-created_at')
        serializer = NotificationSerializer(notifications, many=True)
        return Response(serializer.data)
