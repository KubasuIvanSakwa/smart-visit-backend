from django.shortcuts import render

# backend/notifications/views.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from visitors.models import Notification, CustomUser, Visitor
from django.utils import timezone
from .notifier import send_realtime_notification

class BulkNotifyAPIView(APIView):
    def post(self, request):
        data = request.data

        try:
            visitor_id = data.get("visitor_id")
            host_id = data.get("host_id")
            message = data.get("message")
            extra_data = data.get("data", {})
            channels = data.get("channels", [])

            # Save to database
            notification = Notification.objects.create(
                visitor_id=visitor_id,
                staff_id=host_id,
                message=message,
                data=extra_data,
                sent_at=timezone.now(),
                status="sent",
            )

            # Send actual notification
            send_realtime_notification(
                user=CustomUser.objects.get(id=host_id),
                message=message,
                channel="host_" + str(host_id),
                status="sent",
                data=extra_data,
                event="visitor_checked_in"
            )

            return Response({"success": True, "notification_id": notification.id}, status=status.HTTP_201_CREATED)

        except Exception as e:
            print("Notification error:", e)
            return Response({"success": False, "error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

