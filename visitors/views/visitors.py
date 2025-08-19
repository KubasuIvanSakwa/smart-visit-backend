# backend/visitors/views/visitors.py
from rest_framework import viewsets, generics, views, status
from rest_framework.response import Response
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from rest_framework import filters
from django.utils.timezone import now
from django.http import HttpResponse
from rest_framework import status, permissions
from visitors.models import Visitor,CustomUser
from rest_framework.views import APIView
from visitors.serializers import VisitorSerializer 
from django.shortcuts import get_object_or_404
from io import BytesIO
from notifications.notifier import send_notification
from notifications.models import Notification
from notifications.serializers import NotificationSerializer
from django.db.models.functions import ExtractHour
from django.db.models.functions import TruncMonth
from django.db.models import Count
from django.db.models import F, ExpressionWrapper, DurationField, Avg
from django.utils import timezone
from datetime import datetime
from django.views.decorators.csrf import csrf_exempt
from rest_framework.permissions import AllowAny
from rest_framework.decorators import api_view, permission_classes
from django.utils.decorators import method_decorator
from rest_framework import status, viewsets
from django.views.decorators.http import require_http_methods



from django.db.models import (
    Count, 
    F, 
    
    ExpressionWrapper, 
    DurationField, 
    Avg,
    Q
)
from django.db.models.functions import ExtractHour, TruncMonth
from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A6
from reportlab.lib import colors
import qrcode
import io
import csv
import logging

from ..models import Visitor, VisitorLog, CustomUser
from ..serializers import (
    VisitorSerializer,
    VisitorCheckInSerializer,
    VisitorCheckOutSerializer,
    EmergencyVisitorSerializer,
    VisitorBadgeSerializer
)
from ..permissions import IsAdminUser, IsReceptionistUser
from ..filters import VisitorFilter
from notifications.notifier import (
    send_email_notification,
    trigger_host_notification,
    send_realtime_notification
)
from ..utils.qr_generator import generate_qr_code
from ..utils.badge_designer import design_visitor_badge

logger = logging.getLogger(__name__)

# In visitors/views/visitors.py
class DashboardStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = timezone.now().date()
        
        stats = {
            'currentVisitors': Visitor.objects.filter(status='checked_in').count(),
            'totalCheckedIn': Visitor.objects.filter(
                check_in_time__date=today
            ).count(),
            'totalCheckedOut': Visitor.objects.filter(
                check_out_time__date=today
            ).count(),
            'walkIns': Visitor.objects.filter(
                check_in_time__date=today,
                visitor_type='walk_in'  # Changed from 'type' to 'visitor_type'
            ).count(),
            'preRegistered': Visitor.objects.filter(
                check_in_time__date=today,
                visitor_type='pre_registered'  # Changed from 'type' to 'visitor_type'
            ).count(),
            'pendingApprovals': Visitor.objects.filter(
                status='pending_approval'
            ).count(),
            'avgVisitDuration': self._calculate_avg_duration(),
            'todayCheckIns': Visitor.objects.filter(
                check_in_time__date=today
            ).count(),
            'monthlyTotal': Visitor.objects.filter(
                check_in_time__month=today.month,
                check_in_time__year=today.year
            ).count()
        }

        if request.user.role == 'host':
            stats.update({
                'myTodayTotal': Visitor.objects.filter(
                    check_in_time__date=today,
                    host=request.user
                ).count(),
                'myCurrentVisitors': Visitor.objects.filter(
                    status='checked_in',
                    host=request.user
                ).count(),
                'myPendingApprovals': Visitor.objects.filter(
                    status='pending_approval',
                    host=request.user
                ).count()
            })

        return Response(stats)

    def _calculate_avg_duration(self):
        try:
            result = Visitor.objects.filter(
                check_out_time__isnull=False
            ).aggregate(
                avg_duration=Avg(
                    ExpressionWrapper(
                        F('check_out_time') - F('check_in_time'),
                        output_field=DurationField()
                    )
                )
            )
            return str(result['avg_duration'] or "00:00:00")
        except Exception:
            return "00:00:00"

class VisitorViewSet(viewsets.ModelViewSet):
    """
    Comprehensive API endpoint for visitor management including:
    - Check-in/out functionality
    - Visitor tracking
    - Host notifications
    - QR code generation
    """
    queryset = Visitor.objects.all().order_by('-check_in_time')
    serializer_class = VisitorSerializer
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = [
        'first_name', 
        'last_name', 
        'company', 
        'email', 
        'phone',
        'badge_number'
    ]
    filterset_class = VisitorFilter
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def get_serializer_class(self):
        if self.action == 'create':
            return VisitorCheckInSerializer
        elif self.action == 'check_out':
            return VisitorCheckOutSerializer
        elif self.action == 'badge':
            return VisitorBadgeSerializer
        elif self.action == 'kiosk_checkin':
            return VisitorCheckInSerializer
        return super().get_serializer_class()

    def get_permissions(self):
        if self.action == 'kiosk_checkin':
            return []  # Allow unauthenticated kiosk access
        elif self.action in ['create', 'update', 'partial_update', 'check_out']:
            return [IsAuthenticated(), IsReceptionistUser()]
        elif self.action == 'destroy':
            return [IsAuthenticated(), IsAdminUser()]
        elif self.action in ['badge', 'list', 'retrieve']:
            return [IsAuthenticated()]
        return super().get_permissions()

    def perform_create(self, serializer):
        """Handle visitor check-in with all related operations."""
        with transaction.atomic():
            visitor = serializer.save()
            self._generate_visitor_assets(visitor)
            self._log_visitor_action(visitor, 'CHECK_IN')
            self._notify_related_parties(visitor, 'check_in')

    @action(detail=True, methods=['post'])
    def check_out(self, request, pk=None):
        """Handle visitor check-out procedure."""
        visitor = self.get_object()
        serializer = self.get_serializer(visitor, data=request.data, partial=True)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            visitor = serializer.save()
            self._log_visitor_action(visitor, 'CHECK_OUT')
            self._notify_related_parties(visitor, 'check_out')
            
            # Update visitor duration statistics
            if visitor.check_out_time:
                visitor.duration = (visitor.check_out_time - visitor.check_in_time).total_seconds()
                visitor.save()

        return Response(
            {'message': 'Checked out successfully'}, 
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['get'])
    def badge(self, request, pk=None):
        """Generate visitor badge data (not PDF)."""
        visitor = self.get_object()
        serializer = self.get_serializer(visitor)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='kiosk-checkin')
    def kiosk_checkin(self, request):
        """
        Handle visitor check-in from kiosk (unauthenticated endpoint).
        Allows self-service check-in without login.
        """
        serializer = VisitorCheckInSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            visitor = serializer.save()
            self._generate_visitor_assets(visitor)
            self._log_visitor_action(visitor, 'KIOSK_CHECK_IN')
            self._notify_related_parties(visitor, 'kiosk_check_in')

        return Response({
            'message': 'Visitor checked in via kiosk successfully',
            'visitor_id': visitor.id
        }, status=status.HTTP_201_CREATED)

    def _generate_visitor_assets(self, visitor):
        """Generate all required assets for a new visitor."""
        # Generate QR code
        qr_data = {
            'visitor_id': str(visitor.id),
            'name': visitor.full_name,
            'check_in_time': visitor.check_in_time.isoformat(),
            'company': visitor.company
        }
        qr_img = generate_qr_code(qr_data)
        visitor.qr_image.save(f'qr_{visitor.id}.png', qr_img)

        # Generate badge number if not already set
        if not visitor.badge_number:
            last_badge = Visitor.objects.order_by('-badge_number').first()
            visitor.badge_number = str(int(last_badge.badge_number) + 1) if last_badge and last_badge.badge_number else "1000"


        visitor.save()


    def _log_visitor_action(self, visitor, action):
        """Log visitor activity."""
        user_email = getattr(self.request.user, 'email', None)
        VisitorLog.objects.create(
            visitor=visitor,
            action=action,
            details=f'{action} at {now()} by {user_email if user_email else "system"}',
            user=self.request.user if self.request.user.is_authenticated else None
        )

    def _notify_related_parties(self, visitor, action_type):
        """Notify all relevant parties about visitor status changes."""
        context = {
            'visitor': visitor,
            'action': action_type,
            'timestamp': now()
        }

        # Notify host if assigned
        if visitor.host:
            try:
                host_user = CustomUser.objects.get(id=visitor.host.id)

                # Real-time WebSocket notification to host
                send_realtime_notification(
                    user=host_user,
                    message=f"{visitor.full_name} has just checked in via Kiosk.",
                    event="kiosk_check_in",
                    data={
                        "visitor_id": visitor.id,
                        "check_in_time": str(visitor.check_in_time),
                    },
                    channel=f"user_{host_user.id}",  # Optional override
                )

                # Email and in-app alerts
                trigger_host_notification(recipient=host_user, context=context)
                send_email_notification(recipient=host_user, context=context)

            except CustomUser.DoesNotExist:
                logger.error("Host user does not exist for visitor: %s", visitor.id)

        # Notify reception via WebSocket
        send_realtime_notification(
            user=None,
            message=f"Visitor {visitor.full_name} status update: {action_type}",
            event='visitor_update',
            data={
                'visitor_id': visitor.id,
                'status': visitor.status,
                'action': action_type
            },
            channel='reception'
        )

class VisitorBadgePDFView(views.APIView):
    """Generate printable PDF badge for visitors."""
    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        try:
            visitor = Visitor.objects.select_related('host').get(id=id)
        except Visitor.DoesNotExist:
            return Response(
                {'error': 'Visitor not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        buffer = BytesIO()
        badge = design_visitor_badge(visitor)
        badge.save(buffer)
        
        buffer.seek(0)
        response = HttpResponse(
            buffer,
            content_type='application/pdf'
        )
        response['Content-Disposition'] = f'attachment; filename="badge_{visitor.badge_number}.pdf"'
        return response


class QRCheckInAPIView(views.APIView):

    """Handle QR code-based visitor check-ins."""
    permission_classes = [AllowAny]

    def post(self, request):
        required_fields = ['visitor_id', 'device_id']
        if not all(field in request.data for field in required_fields):
            return Response(
                {"error": f"Required fields: {', '.join(required_fields)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            visitor = Visitor.objects.get(
                id=request.data['visitor_id'],
                status='pre_registered'
            )
        except Visitor.DoesNotExist:
            return Response(
                {"error": "Visitor not found or already checked in"},
                status=status.HTTP_404_NOT_FOUND
            )

        with transaction.atomic():
            visitor.status = 'checked_in'
            visitor.check_in_time = now()
            visitor.check_in_device = request.data['device_id']
            visitor.save()

            VisitorLog.objects.create(
                visitor=visitor,
                action="QR_CHECK_IN",
                details=f"Checked in via QR at {now()} from device {request.data['device_id']}",
                user=None
            )

            # Async notification
            if visitor.host:
                send_realtime_notification.delay(
                    channel=f"host-{visitor.host.id}",
                    event="visitor_checked_in",
                    message=f"{visitor.full_name} has arrived"
                )

        return Response({
            "status": "success",
            "visitor": VisitorSerializer(visitor).data
        })


class EmergencyReportAPIView(views.APIView):
    """Real-time emergency status reporting."""
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        current_visitors = Visitor.objects.filter(
            Q(status='checked_in') | Q(status='in_meeting')
        ).select_related('host')

        serializer = EmergencyVisitorSerializer(current_visitors, many=True)
        
        return Response({
            'timestamp': now().isoformat(),
            'count': current_visitors.count(),
            'visitors': serializer.data,
            'locations': self._get_location_distribution(current_visitors)
        })

    def _get_location_distribution(self, visitors):
        return (
            visitors.values('location')
                   .annotate(count=Count('id'))
                   .order_by('-count')
        )


@api_view(['POST'])
@permission_classes([AllowAny])
def kiosk_checkin_view(request):
    """Self-service kiosk check-in endpoint with comprehensive visitor registration."""
    required_fields = [
        'first_name',
        'phone',
        'purpose',
        'host_id',
        'visitor_type',
        'photo_data',
        'signature_data',
        'plate'  
    ]

    missing_fields = [field for field in required_fields if not request.data.get(field)]
    if missing_fields:
        return Response(
            {"error": f"Missing required fields: {', '.join(missing_fields)}"},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        # Validate host_id
        host_id = request.data.get('host_id')
        try:
            host = CustomUser .objects.get(id=int(host_id))
        except (CustomUser .DoesNotExist, ValueError):
            return Response({"error": "Host not found"}, status=status.HTTP_404_NOT_FOUND)

        # Prepare visitor data for serializer
        visitor_data = {
            'first_name': request.data.get('first_name'),
            'last_name': request.data.get('last_name', ''),
            'phone': request.data.get('phone'),
            'email': request.data.get('email', ''),
            'company': request.data.get('company', ''),
            'purpose': request.data.get('purpose'),
            'host': host.id,
            'visitor_type': request.data.get('visitor_type'),
            'status': 'checked_in',
            'expected_arrival': timezone.now(),
            'check_in_time': timezone.now(),
            'expected_duration': request.data.get('expected_duration', 30),
            'branch': host.branch.id if getattr(host, 'branch', None) else None,
            'plate': request.data.get('plate'),  # Add car plate number here
        }

        serializer = VisitorCheckInSerializer(data=visitor_data, context={'request': request})
        if not serializer.is_valid():
            logger.error(f"VisitorCheckInSerializer errors: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            visitor = serializer.save()

            # Handle photo_data (file or base64)
            photo_data = request.data.get('photo_data')
            if photo_data:
                if hasattr(photo_data, 'read'):  # file upload
                    visitor.photo.save(
                        f"visitor_{visitor.id}_photo.jpg",
                        photo_data,
                        save=True
                    )
                elif isinstance(photo_data, str) and photo_data.startswith('data:image'):
                    import base64
                    from django.core.files.base import ContentFile
                    visitor.photo.save(
                        f"visitor_{visitor.id}_photo.jpg",
                        ContentFile(base64.b64decode(photo_data.split(',')[1])),
                        save=True
                    )

            # Handle signature_data (file or base64)
            signature_data = request.data.get('signature_data')
            if signature_data:
                if hasattr(signature_data, 'read'):  # file upload
                    visitor.signature.save(
                        f"visitor_{visitor.id}_signature.png",
                        signature_data,
                        save=True
                    )
                elif isinstance(signature_data, str) and signature_data.startswith('data:image'):
                    import base64
                    from django.core.files.base import ContentFile
                    visitor.signature.save(
                        f"visitor_{visitor.id}_signature.png",
                        ContentFile(base64.b64decode(signature_data.split(',')[1])),
                        save=True
                    )

            _generate_visitor_assets(visitor)
            _log_visitor_action(visitor, 'KIOSK_CHECK_IN')
            _notify_related_parties(visitor, 'check_in')

            return Response({
                "status": "success",
                "visitor_id": visitor.id,
                "badge_url": f"/api/visitors/{visitor.id}/badge/pdf/",
                "qr_code_url": visitor.qr_image.url if visitor.qr_image else None
            }, status=status.HTTP_201_CREATED)

    except Exception as e:
        logger.error(f"Kiosk check-in failed: {str(e)}", exc_info=True)
        return Response(
            {"error": f"Check-in processing failed: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


def _generate_visitor_assets(visitor):
    """Generate QR code and badge number for visitor."""
    qr_data = {
        'visitor_id': str(visitor.id),
        'name': visitor.full_name,
        'check_in_time': visitor.check_in_time.isoformat(),
        'company': visitor.company
    }
    qr_img = generate_qr_code(qr_data)
    visitor.qr_image.save('qr_' + str(visitor.id) + '.png', qr_img, save=False)


    if not visitor.badge_number:
        last_badge = Visitor.objects.order_by('-badge_number').first()
        visitor.badge_number = (last_badge.badge_number + 1) if last_badge else 1000

    visitor.save()


def _log_visitor_action(visitor, action):
    """Log visitor activity."""
    VisitorLog.objects.create(
        visitor=visitor,
        action=action,
        details=f'{action} via kiosk at {now()}',
        user=None
    )


def _notify_related_parties(visitor, action_type):
    """Notify host and other relevant parties."""
    context = {
        'visitor': visitor,
        'action': action_type,
        'timestamp': now()
    }

    if visitor.host:
        trigger_host_notification(
            recipient=visitor.host,
            context=context
        )
        send_email_notification(
            recipient=visitor.host,
            context=context
        )

    send_realtime_notification(
        channel='reception',
        event='visitor_update',
        data={
            'visitor_id': visitor.id,
            'status': visitor.status,
            'action': action_type
        }
    )


@api_view(['POST'])
@permission_classes([AllowAny])
def offline_checkin_view(request):
    """Handle offline mode check-in synchronization."""
    try:
        visitor = Visitor.objects.get(
            qr_code=request.data.get("qr_code"),
            status='pre_registered'
        )
    except Visitor.DoesNotExist:
        return Response(
            {"error": "Invalid QR code or already checked in"},
            status=status.HTTP_400_BAD_REQUEST
        )

    with transaction.atomic():
        visitor.status = "checked_in"
        visitor.check_in_time = now()
        visitor.offline_checkin = True
        visitor.save()

        VisitorLog.objects.create(
            visitor=visitor,
            action='OFFLINE_CHECKIN',
            details="Synchronized from offline kiosk",
            user=None
        )

    return Response({
        "status": "success",
        "visitor_id": visitor.id
    })
class CurrentVisitorsView(APIView):
    """
    API endpoint that returns currently checked-in visitors.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, format=None):
        current_visitors = Visitor.objects.filter(status='checked_in')
        serializer = VisitorSerializer(current_visitors, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class VisitorDetailView(APIView):
    """
    API endpoint to get a single visitor by ID.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk, format=None):
        visitor = get_object_or_404(Visitor, pk=pk)
        serializer = VisitorSerializer(visitor)
        return Response(serializer.data, status=status.HTTP_200_OK)

class ExportVisitorsCSVView(APIView):
    def get(self, request, *args, **kwargs):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="visitors.csv"'

        writer = csv.writer(response)
        writer.writerow(['Name', 'Company', 'Phone'])

        for visitor in Visitor.objects.all():
            writer.writerow([visitor.name, visitor.company, visitor.phone])

        return response
from django.db.models.functions import ExtractHour, TruncMonth
from django.db.models import Count
from rest_framework.views import APIView
from rest_framework.response import Response
from visitors.models import Visitor
from datetime import datetime

class PeakHoursView(APIView):
    def get(self, request, *args, **kwargs):
        # Get the raw data from database
        raw_data = (
            Visitor.objects
            .annotate(hour=ExtractHour('check_in_time'))
            .values('hour')
            .annotate(count=Count('id'))
            .order_by('hour')
        )
        
        # Format the data for frontend
        formatted_data = []
        for entry in raw_data:
            hour = entry['hour']
            # Convert 24-hour format to 12-hour AM/PM format
            if hour == 0:
                hour_str = '12 AM'
            elif hour < 12:
                hour_str = f'{hour} AM'
            elif hour == 12:
                hour_str = '12 PM'
            else:
                hour_str = f'{hour-12} PM'
                
            formatted_data.append({
                'hour': hour_str,
                'visitors': entry['count']
            })
        
        return Response(formatted_data)

class MonthlyTrendsView(APIView):
    def get(self, request, *args, **kwargs):
        # Get the raw data from database
        raw_data = (
            Visitor.objects
            .annotate(month=TruncMonth('check_in_time'))
            .values('month')
            .annotate(visits=Count('id'))
            .order_by('month')
        )
        
        # Format the data for frontend
        formatted_data = []
        for entry in raw_data:
            month = entry['month']
            month_str = month.strftime('%b')  
            
            formatted_data.append({
                'month': month_str,
                'visitors': entry['visits']
            })
        
        return Response(formatted_data)

class NotifyVisitorView(APIView):
    def post(self, request, *args, **kwargs):
        visitor_id = request.data.get('visitor_id')
        message = request.data.get('message')

        try:
            visitor = Visitor.objects.get(id=visitor_id)
            send_notification(visitor, message)
            return Response({'message': 'Notification sent'}, status=status.HTTP_200_OK)
        except Visitor.DoesNotExist:
            return Response({'error': 'Visitor not found'}, status=status.HTTP_404_NOT_FOUND)

class NotificationViewSet(viewsets.ModelViewSet):
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer

class SubscribeToNotificationsView(APIView):
    def post(self, request, *args, **kwargs):
        visitor_id = request.data.get('visitor_id')
        subscribe = request.data.get('subscribe', True)

        try:
            visitor = Visitor.objects.get(id=visitor_id)
            visitor.subscribed_to_notifications = subscribe
            visitor.save()
            return Response({'message': 'Subscription updated.'})
        except Visitor.DoesNotExist:
            return Response({'error': 'Visitor not found.'}, status=status.HTTP_404_NOT_FOUND)

class NotificationPreferencesView(APIView):
    def get(self, request, *args, **kwargs):
        visitor_id = request.query_params.get('visitor_id')
        visitor = Visitor.objects.filter(id=visitor_id).values('id', 'notification_method', 'subscribed_to_notifications').first()
        if not visitor:
            return Response({'error': 'Visitor not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response(visitor)

    def post(self, request, *args, **kwargs):
        visitor_id = request.data.get('visitor_id')
        method = request.data.get('method', 'email')
        try:
            visitor = Visitor.objects.get(id=visitor_id)
            visitor.notification_method = method
            visitor.save()
            return Response({'message': 'Preferences updated'})
        except Visitor.DoesNotExist:
            return Response({'error': 'Visitor not found'}, status=status.HTTP_404_NOT_FOUND)
class PendingApprovalsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = Visitor.objects.filter(status='pending_approval')
        
        if request.user.role == 'host':
            queryset = queryset.filter(host=request.user)
            
        serializer = VisitorSerializer(queryset, many=True)
        return Response(serializer.data)

class EmergencyReportPDFView(APIView):
    """
    Generates a PDF emergency report listing all currently checked-in visitors
    with their contact details and host information.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        # Get current visitors
        current_visitors = Visitor.objects.filter(
            Q(status='checked_in') | Q(status='in_meeting')
        ).select_related('host')

        # Create PDF buffer
        buffer = BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=letter)
        
        # Set up styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'Title',
            parent=styles['Heading1'],
            alignment=1,
            spaceAfter=20
        )
        
        # Add title
        title = Paragraph(
            f"Emergency Visitor Report - {now().strftime('%Y-%m-%d %H:%M')}",
            title_style
        )
        title.wrapOn(pdf, 500, 50)
        title.drawOn(pdf, 50, 750)
        
        # Create table data
        table_data = [
            [
                'Visitor Name', 
                'Company', 
                'Phone', 
                'Email', 
                'Host', 
                'Check-in Time',
                'Location'
            ]
        ]
        
        for visitor in current_visitors:
            table_data.append([
                visitor.full_name,
                visitor.company or 'N/A',
                visitor.phone or 'N/A',
                visitor.email or 'N/A',
                visitor.host.get_full_name() if visitor.host else 'N/A',
                visitor.check_in_time.strftime('%H:%M'),
                visitor.location or 'N/A'
            ])
        
        # Create table
        table = Table(table_data, colWidths=[100, 80, 80, 120, 100, 60, 80])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
        ]))
        
        # Draw table
        table.wrapOn(pdf, 500, 600)
        table.drawOn(pdf, 50, 650 - len(current_visitors)*20)
        
        # Add footer
        pdf.setFont('Helvetica', 8)
        pdf.drawString(50, 30, f"Generated at: {now().strftime('%Y-%m-%d %H:%M:%S')}")
        pdf.drawRightString(550, 30, f"Total Visitors: {len(current_visitors)}")
        
        # Finalize PDF
        pdf.showPage()
        pdf.save()
        
        # Prepare response
        buffer.seek(0)
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = (
            'attachment; '
            f'filename="emergency_visitor_report_{now().strftime("%Y%m%d_%H%M")}.pdf"'
        )
        return response
    

class VisitorStatsView(APIView):
    """
    API endpoint that provides comprehensive visitor statistics including:
    - Daily/Monthly visitor counts
    - Average visit duration
    - Visitor type distribution
    - Peak hours analysis
    - Host with most visitors
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Date ranges
        today = timezone.now().date()
        thirty_days_ago = today - timedelta(days=30)
        one_year_ago = today - timedelta(days=365)

        # Basic counts
        total_visitors = Visitor.objects.count()
        current_visitors = Visitor.objects.filter(status='checked_in').count()
        pre_registered = Visitor.objects.filter(visitor_type='pre_registered').count()
        walk_ins = Visitor.objects.filter(visitor_type='walk_in').count()

        # Time-based statistics
        daily_stats = self._get_daily_stats(thirty_days_ago)
        monthly_stats = self._get_monthly_stats(one_year_ago)
        peak_hours = self._get_peak_hours()
        avg_duration = self._get_avg_duration()

        # Host statistics
        top_hosts = (
            Visitor.objects.values('host__first_name', 'host__last_name')
            .annotate(total=Count('id'))
            .order_by('-total')[:5]
        )

        return Response({
            'summary': {
                'total_visitors': total_visitors,
                'current_visitors': current_visitors,
                'pre_registered': pre_registered,
                'walk_ins': walk_ins,
                'avg_visit_duration': avg_duration,
            },
            'daily_stats': daily_stats,
            'monthly_stats': monthly_stats,
            'peak_hours': peak_hours,
            'top_hosts': top_hosts,
        })

    def _get_daily_stats(self, start_date):
        return (
            Visitor.objects
            .filter(check_in_time__date__gte=start_date)
            .annotate(day=TruncDay('check_in_time'))
            .values('day')
            .annotate(
                total=Count('id'),
                pre_registered=Count('id', filter=Q(visitor_type='pre_registered')),
                walk_ins=Count('id', filter=Q(visitor_type='walk_in'))
            )
            .order_by('day')
        )

    def _get_monthly_stats(self, start_date):
        return (
            Visitor.objects
            .filter(check_in_time__date__gte=start_date)
            .annotate(month=TruncMonth('check_in_time'))
            .values('month')
            .annotate(
                total=Count('id'),
                avg_duration=Avg(
                    ExpressionWrapper(
                        F('check_out_time') - F('check_in_time'),
                        output_field=DurationField()
                    )
                )
            )
            .order_by('month')
        )

    def _get_peak_hours(self):
        return (
            Visitor.objects
            .annotate(hour=ExtractHour('check_in_time'))
            .values('hour')
            .annotate(count=Count('id'))
            .order_by('-count')[:5]
        )

    def _get_avg_duration(self):
        result = Visitor.objects.filter(
            check_out_time__isnull=False
        ).aggregate(
            avg_duration=Avg(
                ExpressionWrapper(
                    F('check_out_time') - F('check_in_time'),
                    output_field=DurationField()
                )
            )
        )
        return str(result['avg_duration']).split('.')[0] if result['avg_duration'] else "00:00:00"
    
class VisitorReportsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = timezone.now().date()
        week_ago = today - timedelta(days=6)
        month_ago = today.replace(day=1)

        # Daily stats for the last 7 days
        daily = []
        for i in range(7):
            day = week_ago + timedelta(days=i)
            visitors = Visitor.objects.filter(check_in_time__date=day)
            walk_ins = visitors.filter(visitor_type='walk_in').count()
            pre_registered = visitors.filter(visitor_type='pre_registered').count()
            avg_duration = visitors.aggregate(avg=Avg('visit_duration'))['avg'] or 0
            daily.append({
                'date': str(day),
                'visitors': visitors.count(),
                'walkIns': walk_ins,
                'preRegistered': pre_registered,
                'avgDuration': f"{round(avg_duration, 1)}h" if avg_duration else "0h"
            })

        # Hourly stats for today
        hourly = []
        for hour in range(8, 18):  # 8 AM to 5 PM
            start = timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.min.time())) + timedelta(hours=hour)
            end = start + timedelta(hours=1)
            visitors = Visitor.objects.filter(check_in_time__gte=start, check_in_time__lt=end)
            check_ins = visitors.count()
            check_outs = visitors.filter(status='checked_out').count()
            hourly.append({
                'hour': f"{hour % 12 or 12} {'AM' if hour < 12 else 'PM'}",
                'visitors': check_ins,
                'checkIns': check_ins,
                'checkOuts': check_outs,
            })

        # Monthly stats for the current year
        monthly = []
        for month in range(1, today.month + 1):
            start = today.replace(month=month, day=1)
            if month == 12:
                end = today.replace(year=today.year + 1, month=1, day=1)
            else:
                end = today.replace(month=month + 1, day=1)
            visitors = Visitor.objects.filter(check_in_time__gte=start, check_in_time__lt=end)
            walk_ins = visitors.filter(visitor_type='walk_in').count()
            pre_registered = visitors.filter(visitor_type='pre_registered').count()
            avg_duration = visitors.aggregate(avg=Avg('visit_duration'))['avg'] or 0
            monthly.append({
                'month': start.strftime('%b %Y'),
                'visitors': visitors.count(),
                'walkIns': walk_ins,
                'preRegistered': pre_registered,
                'avgDuration': f"{round(avg_duration, 1)}h" if avg_duration else "0h"
            })

        # Host performance
        host_performance = []
        hosts = CustomUser.objects.filter(role='host')
        for host in hosts:
            visitors = Visitor.objects.filter(host=host)
            total_visitors = visitors.count()
            avg_duration = visitors.aggregate(avg=Avg('visit_duration'))['avg'] or 0
            satisfaction = 4.5  # Placeholder, replace with real calculation if available
            host_performance.append({
                'name': host.get_full_name(),
                'totalVisitors': total_visitors,
                'avgDuration': f"{round(avg_duration, 1)}h" if avg_duration else "0h",
                'satisfaction': satisfaction,
            })

        # Company frequency
        companies = Visitor.objects.values('company').annotate(
            visits=Count('id'),
            lastVisit=Max('check_in_time')
        ).order_by('-visits')[:10]
        company_frequency = [
            {
                'company': c['company'],
                'visits': c['visits'],
                'lastVisit': c['lastVisit'].strftime('%Y-%m-%d') if c['lastVisit'] else ''
            }
            for c in companies
        ]

        data = {
            'daily': daily,
            'hourly': hourly,
            'monthly': monthly,
            'host_performance': host_performance,
            'company_frequency': company_frequency,
        }
        return Response(data)