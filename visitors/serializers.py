from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core import exceptions
from .models import CustomUser, Visitor, FormField, UserProfile, VisitorLog
from rest_framework import serializers
from .models import UserProfile 
from visitors.models import Notification
from django.core.files.base import ContentFile
import base64
import io
import os
from PIL import Image

User = get_user_model()

# ========== DEFAULT IMAGES ==========

# Default profile image (simple gray silhouette - 100x100px)
DEFAULT_PHOTO_BASE64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAGQAAABkCAYAAABw4pVUAAAACXBIWXMAAAsTAAALEwEAmpwYAAAA3klEQVR4nO3WQQ0AIAwEwdMf2p9aCkEGBHLv7sz77+w4GBwOh8PhcDgcDofD4XA4HA6Hw+FwOBwOh8PhcDgcDofD4XA4HA6Hw+FwOBwOh8PhcDgcDofD4XA4HA6Hw+FwOBwOh8PhcDgcDofD4XA4HA6Hw+FwOBwOh8PhcDgcDofD4XA4HA6Hw+FwOBwOh8PhcDgcDofD4XA4HA6Hw+FwOBwOh8PhcDgcDofD4XA4HA6Hw+FwOBwOh8PhcDgcDofD4XA4HA6Hw+FwOBwOh8PhcDgcDofD4XA4HA6Hw+FwOByO4wFm4A5CIW5WsgAAAABJRU5ErkJggg=="

# Default signature placeholder (simple text "Signature" - 200x50px)
DEFAULT_SIGNATURE_BASE64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAMgAAAAyCAYAAAAZUZThAAAACXBIWXMAAAsTAAALEwEAmpwYAAAA5ElEQVR4nO3TMQEAAAzCsOFf2h8dCqZlwQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAE4N8YcCZAk3Q3YAAAAASUVORK5CYII="

# ========== CUSTOM BASE64 IMAGE FIELD ==========

class Base64ImageField(serializers.ImageField):
    """
    Custom field to handle base64 encoded images for both input and output
    """
    
    def __init__(self, default_image=None, **kwargs):
        self.default_image = default_image
        super().__init__(**kwargs)
    
    def to_internal_value(self, data):
        # Handle base64 string input
        if isinstance(data, str) and data.startswith('data:image'):
            # Extract format and base64 data
            format, imgstr = data.split(';base64,')
            ext = format.split('/')[-1]
            
            # Decode base64 string
            try:
                decoded_data = base64.b64decode(imgstr)
                
                # Create ContentFile
                data = ContentFile(decoded_data, name=f'temp.{ext}')
                
            except (ValueError, base64.binascii.Error):
                raise serializers.ValidationError('Invalid base64 image data')
                
        return super().to_internal_value(data)
    
    def to_representation(self, value):
        """Return image as base64 string if exists, otherwise return default."""
        if value and hasattr(value, 'path') and os.path.exists(value.path):
            try:
                with Image.open(value.path) as img:
                    # Convert to RGB if necessary
                    if img.mode in ('RGBA', 'LA'):
                        rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                        rgb_img.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                        img = rgb_img
                    
                    # Determine format
                    img_format = img.format or 'JPEG'
                    if img_format.upper() == 'PNG':
                        mime_type = 'image/png'
                    elif img_format.upper() in ('JPG', 'JPEG'):
                        mime_type = 'image/jpeg'
                    else:
                        mime_type = f'image/{img_format.lower()}'
                    
                    # Convert to base64
                    buffer = io.BytesIO()
                    img.save(buffer, format=img_format)
                    image_data = buffer.getvalue()
                    encoded_string = base64.b64encode(image_data).decode('utf-8')
                    return f"data:{mime_type};base64,{encoded_string}"
            except (IOError, OSError, ValueError):
                pass
        
        # Return default image if no image exists
        return self.default_image

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
    photo = Base64ImageField(required=False, allow_null=True, default_image=DEFAULT_PHOTO_BASE64)
    signature = Base64ImageField(required=False, allow_null=True, default_image=DEFAULT_SIGNATURE_BASE64)
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

    def validate_photo(self, value):
        """Validate photo file size"""
        if value and hasattr(value, 'size') and value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError("Photo file size must be less than 5MB")
        return value
    
    def validate_signature(self, value):
        """Validate signature file size"""
        if value and hasattr(value, 'size') and value.size > 2 * 1024 * 1024:
            raise serializers.ValidationError("Signature file size must be less than 2MB")
        return value

class VisitorCheckInSerializer(serializers.ModelSerializer):
    photo = Base64ImageField(required=False, allow_null=True, default_image=DEFAULT_PHOTO_BASE64)
    signature = Base64ImageField(required=False, allow_null=True, default_image=DEFAULT_SIGNATURE_BASE64)

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
            "photo",
            "signature"
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
    photo = Base64ImageField(read_only=True)
    signature = Base64ImageField(read_only=True)
    qr_image = Base64ImageField(read_only=True)

    class Meta:
        model = Visitor
        fields = [
            'id', 'name', 'company', 'email', 'phone',
            'host_name', 'check_in_time', 'badge_number',
            'status', 'qr_code', 'qr_image', 'photo', 'signature'
        ]
        read_only_fields = ['qr_code', 'qr_image']

class EmergencyVisitorSerializer(serializers.ModelSerializer):
    full_name = serializers.ReadOnlyField()
    photo = Base64ImageField(read_only=True)
    signature = Base64ImageField(read_only=True)

    class Meta:
        model = Visitor
        fields = [
            'full_name', 'company', 'phone', 'check_in_time',
            'host', 'badge_number', 'status', 'photo', 'signature'
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