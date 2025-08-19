from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core import exceptions
from .models import CustomUser, Visitor, FormField, UserProfile, VisitorLog
from rest_framework import serializers
from .models import UserProfile 
from visitors.models import Notification

User = get_user_model()

# ========== USER PROFILE SERIALIZER ==========

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = '__all__'

# ========== AUTHENTICATION SERIALIZERS ==========

class UserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(read_only=True)
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'profile']

from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import authenticate

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = 'email'  # IMPORTANT: use email

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")

        user = authenticate(username=email, password=password)  # authenticate uses EmailBackend
        if not user:
            raise AuthenticationFailed('Invalid email or password')

        data = super().validate(attrs)
        data.update({
            'user_id': user.id,
            'email': user.email,
            'role': user.role,
            'first_name': user.first_name,
            'last_name': user.last_name
        })
        return data


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

class RegisterSerializer(serializers.ModelSerializer):
    company = serializers.CharField(write_only=True)
    phone = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)
    profile = UserProfileSerializer(read_only=True)

    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'email', 'password', 'confirm_password', 'company', 'phone', 'profile']
        extra_kwargs = {
            'password': {'write_only': True},
        }

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already exists.")
        return value

    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError("Passwords do not match.")
        return data

    def create(self, validated_data):
        company = validated_data.pop('company')
        phone = validated_data.pop('phone')
        validated_data.pop('confirm_password')

        user = User.objects.create_user(
            username=validated_data['email'],
            email=validated_data['email'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            password=validated_data['password']
        )

        UserProfile.objects.create(user=user, company=company, phone=phone)
        return user

class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

class PasswordResetConfirmSerializer(serializers.Serializer):
    new_password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    new_password2 = serializers.CharField(write_only=True, required=True)
    token = serializers.CharField(write_only=True, required=True)
    uidb64 = serializers.CharField(write_only=True, required=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password2']:
            raise serializers.ValidationError({"new_password": "Password fields didn't match."})
        return attrs

class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True, required=True)
    new_password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    new_password2 = serializers.CharField(write_only=True, required=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password2']:
            raise serializers.ValidationError({"new_password": "Password fields didn't match."})
        return attrs

# ========== VISITOR MANAGEMENT SERIALIZERS ==========

class VisitorSerializer(serializers.ModelSerializer):
    duration = serializers.SerializerMethodField(
        help_text="Duration of the visit, e.g., '1h 10m'. Calculated if checked out, otherwise '—'."
    )

    class Meta:
        model = Visitor
        fields = '__all__'
        read_only_fields = ['qr_code', 'qr_image']

    def get_duration(self, obj):
        if obj.check_out_time and obj.check_in_time:
            delta = obj.check_out_time - obj.check_in_time
            seconds = int(delta.total_seconds())
            hours, remainder = divmod(seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            return f"{hours}h {minutes}m"
        return "—"

class VisitorCheckInSerializer(serializers.ModelSerializer):
    class Meta:
        model = Visitor
        fields = [
            "first_name",
            "last_name",
            "email",
            "phone",
            "company",
            "purpose", 
            "branch",
            "id_number",
            
        ]

class VisitorCheckOutSerializer(serializers.ModelSerializer):
    class Meta:
        model = Visitor
        fields = ['status', 'check_out_time']

    def validate(self, data):
        if self.instance.status == 'checked_out':
            raise serializers.ValidationError("Visitor is already checked out.")
        return data

class VisitorBadgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Visitor
        fields = [
            'id', 'name', 'company', 'email', 'phone',
            'host_name', 'check_in_time', 'badge_number',
            'status', 'qr_code', 'qr_image',
        ]
        read_only_fields = ['qr_code', 'qr_image']

class EmergencyVisitorSerializer(serializers.ModelSerializer):
    full_name = serializers.ReadOnlyField()

    class Meta:
        model = Visitor
        fields = [
            'full_name', 'company', 'phone', 'check_in_time',
            'host', 'badge_number', 'status'
        ]

# ========== FORM & LOGGING SERIALIZERS ==========

class FormFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = FormField
        fields = '__all__'

class VisitorLogSerializer(serializers.ModelSerializer):
    visitor_name = serializers.CharField(source='visitor.name', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)

    class Meta:
        model = VisitorLog
        fields = [
            'id', 'visitor', 'visitor_name', 'action',
            'details', 'user', 'user_email', 'timestamp'
        ]

class VisitorReportSerializer(serializers.Serializer):
    daily = serializers.ListField()
    hourly = serializers.ListField()
    monthly = serializers.ListField()
    host_performance = serializers.ListField()
    company_frequency = serializers.ListField()

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = '__all__'
