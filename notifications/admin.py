from django.contrib import admin
from django.utils.html import format_html
from .models import Notification

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('message_truncated', 'colored_recipient', 'channel', 'status', 'is_read', 'created_at')
    list_filter = ('status', 'channel', 'created_at')
    search_fields = ('message', 'staff__email', 'visitor__id')  # safer than visitor__email
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at', 'sent_at', 'read_at')
    
    fieldsets = (
        (None, {
            'fields': ('staff', 'visitor', 'message')
        }),
        ('Delivery Info', {
            'fields': ('channel', 'status', 'sent_at', 'read_at')
        }),
    )

    @admin.display(description='Message')
    def message_truncated(self, obj):
        return obj.message[:75] + '...' if len(obj.message) > 75 else obj.message
    
    @admin.display(description='Recipient')
    def colored_recipient(self, obj):
        """Show staff in blue, visitors in green"""
        if obj.staff:
            return format_html('<span style="color: #1E90FF; font-weight: bold;">Staff: {}</span>', obj.staff.email)
        elif obj.visitor:
            label = getattr(obj.visitor, 'email', f"Visitor {obj.visitor.id}")
            return format_html('<span style="color: #228B22; font-weight: bold;">Visitor: {}</span>', label)
        return format_html('<span style="color: gray;">Unknown</span>')

    @admin.display(boolean=True, description="Read")
    def is_read(self, obj):
        return obj.is_read
