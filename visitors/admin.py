from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    Branch,
    CustomUser,
    Visitor,
    VisitorLog,
    FormField,
    VisitorSetting,
    Blacklist,
    UserProfile,
    
)

# --- Custom User Admin ---
@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {
            'fields': ('first_name', 'last_name', 'phone', 'department', 'job_title', 'profile_picture')
        }),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'is_verified', 'role', 'groups', 'user_permissions'),
        }),
        ('Important dates', {'fields': ('last_login',)}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'is_staff', 'is_active')
        }),
    )
    list_display = ('email', 'first_name', 'last_name', 'role', 'is_staff', 'is_active')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'role')
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('email',)
    filter_horizontal = ('groups', 'user_permissions',)

# --- Visitor Admin ---
@admin.register(Visitor)
class VisitorAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'host', 'check_in_time', 'check_out_time', 'status')
    list_filter = ('status', 'visitor_type')
    search_fields = ('first_name', 'last_name', 'email', 'phone')

# --- Visitor Log Admin ---
@admin.register(VisitorLog)
class VisitorLogAdmin(admin.ModelAdmin):
    list_display = ('visitor', 'action', 'timestamp')
    list_filter = ('action',)
    search_fields = ('visitor__first_name', 'visitor__last_name')

# --- Form Field Admin ---
@admin.register(FormField)
class FormFieldAdmin(admin.ModelAdmin):
    list_display = ('label', 'field_type', 'required', 'is_active')
    list_editable = ('required', 'is_active')
    search_fields = ('label',)

# --- Blacklist Admin ---
@admin.register(Blacklist)
class BlacklistAdmin(admin.ModelAdmin):
    list_display = ('get_visitor_name', 'reason', 'added_at')
    search_fields = ('visitor__first_name', 'visitor__last_name', 'reason')

    @admin.display(description='Visitor Name')
    def get_visitor_name(self, obj):
        return obj.visitor.full_name

# --- User Profile Admin ---
@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'company', 'phone')
    search_fields = ('user__username', 'company')

# --- Visitor Setting Admin ---
@admin.register(VisitorSetting)
class VisitorSettingAdmin(admin.ModelAdmin):
    list_display = ('require_photo', 'default_checkin_duration', 'enable_pre_registration')

# --- Branch Admin ---
@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ('name', 'address', 'latitude', 'longitude', 'is_active')
    search_fields = ('name', 'address')
    list_filter = ('is_active',)

# # --- Notification Admin ---
# @admin.register(Notification)
# class NotificationAdmin(admin.ModelAdmin):
#     list_display = ('recipient', 'message', 'created_at', 'is_read')
#     list_filter = ('is_read',)
#     search_fields = ('recipient__email', 'message')