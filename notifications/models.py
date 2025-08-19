from django.db import models
from visitors.models import CustomUser, Visitor

class Notification(models.Model):
    # Recipient can be either staff or visitor
    staff = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="staff_notifications",
        verbose_name="Staff Recipient"
    )
    visitor = models.ForeignKey(
        Visitor,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="visitor_notifications",
        verbose_name="Visitor Recipient"
    )
    
    # Message content
    message = models.TextField(verbose_name="Notification Content")
    
    # Status fields
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('read', 'Read'),
        ('failed', 'Failed'),
    ]
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
        verbose_name="Delivery Status"
    )
    
    # Channel/delivery method
    CHANNEL_CHOICES = [
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('app', 'In-App'),
        ('all', 'All Channels'),
    ]
    channel = models.CharField(
        max_length=50,
        choices=CHANNEL_CHOICES,
        verbose_name="Delivery Channel"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")
    sent_at = models.DateTimeField(null=True, blank=True, verbose_name="Sent At")
    read_at = models.DateTimeField(null=True, blank=True, verbose_name="Read At")
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
    
    def __str__(self):
        recipient = self.staff.email if self.staff else f"Visitor {self.visitor.id}" if self.visitor else "Unknown"
        return f"{self.message[:50]}... (to: {recipient})"
    
    @property
    def is_read(self):
        return self.status == 'read' and self.read_at is not None
    
    @property
    def recipient(self):
        return self.staff or self.visitor