from rest_framework import serializers
from .models import Notification
from visitors.models import Notification

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'message', 'recipient', 'created_at']