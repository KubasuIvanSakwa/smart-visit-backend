from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.files import File
from django.utils.translation import gettext_lazy as _
from django.core.validators import RegexValidator
from io import BytesIO
import qrcode
import uuid


class CustomUserManager(BaseUserManager):
    """Custom user manager that uses email instead of username with enhanced superuser creation"""
    
    def create_user(self, email, password=None, **extra_fields):
        """
        Creates and saves a User with the given email and password.
        """
        if not email:
            raise ValueError(_('The Email must be set'))
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """
        Creates and saves a superuser with the given email and password.
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        
        # Set admin role if the model has Role choices
        if hasattr(self.model, 'Role'):
            extra_fields.setdefault('role', self.model.Role.ADMIN)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))
        
        return self.create_user(email, password, **extra_fields)


class CustomUser(AbstractUser):
    """Extended user model using email as username with comprehensive profile fields"""
    
    class Role(models.TextChoices):
        ADMIN = 'admin', _('Administrator')
        RECEPTIONIST = 'receptionist', _('Receptionist')
        HOST = 'host', _('Host')
        SECURITY = 'security', _('Security')
        USER = 'user', _('Regular User')
    
    # Authentication fields
    username = None  # Disable username field
    email = models.EmailField(unique=True, verbose_name=_("Email Address"))
    
    # Profile fields
    first_name = models.CharField(max_length=150, blank=True, verbose_name=_("First Name"))
    last_name = models.CharField(max_length=150, blank=True, verbose_name=_("Last Name"))
    phone = models.CharField(
        max_length=20,
        validators=[RegexValidator(r'^\+?1?\d{9,15}$', message=_("Enter a valid phone number"))],
        blank=True, null=True, verbose_name=_("Phone Number")
    )
    department = models.CharField(max_length=100, blank=True, null=True, verbose_name=_("Department"))
    job_title = models.CharField(max_length=100, blank=True, null=True, verbose_name=_("Job Title"))
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.USER,
        verbose_name=_("User Role")
    )
    profile_picture = models.ImageField(
        upload_to='profile_pics/',
        blank=True, null=True,
        verbose_name=_("Profile Picture")
    )
    is_verified = models.BooleanField(default=False, verbose_name=_("Verified Status"))
    branch = models.ForeignKey(
        'Branch',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='staff_members',
        verbose_name=_("Branch")
    )
    
    # System fields
    is_active = models.BooleanField(default=True, verbose_name=_("Active Status"))
    date_joined = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Date Joined"),
        editable=False  # Explicitly non-editable
    )
    last_login = models.DateTimeField(null=True, blank=True, verbose_name=_("Last Login"))
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []  # No extra required fields
    
    objects = CustomUserManager()

    class Meta:
        verbose_name = _("User")
        verbose_name_plural = _("Users")
        ordering = ['last_name', 'first_name']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['last_name', 'first_name']),
            models.Index(fields=['role']),
        ]

    def __str__(self):
        full_name = f"{self.first_name} {self.last_name}".strip()
        if full_name:
            return f"{full_name} ({self.get_role_display()})"
        return self.email

    @property
    def full_name(self):
        """Returns the person's full name."""
        return f"{self.first_name} {self.last_name}".strip()

    def get_short_name(self):
        """Returns the short name for the user."""
        return self.first_name or self.email.split('@')[0]
class Branch(models.Model):
    """Model representing company branches/locations"""
    name = models.CharField(
        max_length=100,
        verbose_name=_("Branch Name")
    )
    address = models.TextField(
        verbose_name=_("Address")
    )
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        blank=True,
        null=True,
        verbose_name=_("Latitude")
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        blank=True,
        null=True,
        verbose_name=_("Longitude")
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Active Status")
    )

    class Meta:
        verbose_name = _("Branch")
        verbose_name_plural = _("Branches")
        ordering = ['name']

    def __str__(self):
        return self.name


class Visitor(models.Model):
    """Model representing a visitor"""
    class Status(models.TextChoices):
        PRE_REGISTERED = 'pre_registered', _('Pre-Registered')
        CHECKED_IN = 'checked_in', _('Checked In')
        IN_MEETING = 'in_meeting', _('In Meeting')
        CHECKED_OUT = 'checked_out', _('Checked Out')
        BLACKLISTED = 'blacklisted', _('Blacklisted')

    class VisitorType(models.TextChoices):
        GUEST = 'guest', _('Guest')
        CONTRACTOR = 'contractor', _('Contractor')
        VENDOR = 'vendor', _('Vendor')
        INTERVIEW = 'interview', _('Interviewee')
        DELIVERY = 'delivery', _('Delivery')

    class IDType(models.TextChoices):
        NATIONAL_ID = 'national_id', _('National ID')
        PASSPORT = 'passport', _('Passport')
        DRIVER_LICENSE = 'driver_license', _('Driver License')
        OTHER = 'other', _('Other')

    first_name = models.CharField(
        max_length=50,
        verbose_name=_("First Name")
    )
    last_name = models.CharField(
        max_length=50,
        verbose_name=_("Last Name")
    )
    email = models.EmailField(
        blank=True,
        null=True,
        verbose_name=_("Email Address")
    )
    phone = models.CharField(
        max_length=20,
        validators=[RegexValidator(r'^\+?1?\d{9,15}$', message=_("Enter a valid phone number"))],
        verbose_name=_("Phone Number")
    )
    company = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_("Company")
    )
    id_number = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name=_("ID/Passport Number")
    )
    id_type = models.CharField(
        max_length=30,
        blank=True,
        null=True,
        choices=IDType.choices,
        verbose_name=_("ID Type")
    )
    visitor_type = models.CharField(
        max_length=20,
        choices=VisitorType.choices,
        default=VisitorType.GUEST,
        verbose_name=_("Visitor Type")
    )
    host = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        related_name='visitors',
        null=True,
        verbose_name=_("Host")
    )
    branch = models.ForeignKey(
        Branch,
        on_delete=models.SET_NULL,
        null=True,
        related_name='visitors',
        verbose_name=_("Branch")
    )
    purpose = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Visit Purpose")
    )
    expected_arrival = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_("Expected Arrival Time")
    )
    check_in_time = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Check-in Time")
    )
    check_out_time = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_("Check-out Time")
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.CHECKED_IN,
        verbose_name=_("Status")
    )
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Additional Notes")
    )
    photo = models.ImageField(
        upload_to='visitor_photos/',
        blank=True,
        null=True,
        verbose_name=_("Photo")
    )
    signature = models.ImageField(
        upload_to='visitor_signatures/',
        blank=True,
        null=True,
        verbose_name=_("Signature")
    )
    nda = models.FileField(
        upload_to='nda_documents/',
        blank=True,
        null=True,
        verbose_name=_("NDA Document")
    )
    health_declaration = models.BooleanField(
        default=False,
        verbose_name=_("Health Declaration Signed")
    )
    temperature = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        blank=True,
        null=True,
        verbose_name=_("Temperature (°C)")
    )
    qr_code = models.CharField(
        max_length=100,
        unique=True,
        blank=True,
        verbose_name=_("QR Code")
    )
    qr_image = models.ImageField(
        upload_to='qr_codes/',
        blank=True,
        null=True,
        verbose_name=_("QR Code Image")
    )
    badge_printed = models.BooleanField(
        default=False,
        verbose_name=_("Badge Printed")
    )
    badge_number = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name=_("Badge Number")
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created At")
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Updated At")
    )

    class Meta:
        verbose_name = _("Visitor")
        verbose_name_plural = _("Visitors")
        ordering = ['-check_in_time']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['check_in_time']),
            models.Index(fields=['host']),
            models.Index(fields=['visitor_type']),
        ]

    def __str__(self):
        return f"{self.full_name} - {self.get_status_display()}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    full_name.fget.short_description = _("Full Name")

    @property
    def duration(self):
        if self.check_out_time:
            return self.check_out_time - self.check_in_time
        return None
    duration.fget.short_description = _("Visit Duration")

    def save(self, *args, **kwargs):
        if not self.qr_code:
            self.qr_code = f"KREP-{uuid.uuid4().hex[:8].upper()}"
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(self.qr_code)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            filename = f"{self.qr_code}.png"
            buffer.seek(0)
            self.qr_image.save(filename, File(buffer), save=False)
        super().save(*args, **kwargs)


class VisitorLog(models.Model):
    """Model representing logs for visitor actions"""
    class Action(models.TextChoices):
        PRE_REGISTER = 'pre_register', _('Pre-Registered')
        CHECK_IN = 'check_in', _('Checked In')
        CHECK_OUT = 'check_out', _('Checked Out')
        STATUS_CHANGE = 'status_change', _('Status Changed')
        DOCUMENT_UPLOAD = 'document_upload', _('Document Uploaded')
        BLACKLISTED = 'blacklisted', _('Blacklisted')
        NOTIFICATION_SENT = 'notification_sent', _('Notification Sent')

    visitor = models.ForeignKey(
        Visitor,
        on_delete=models.CASCADE,
        related_name='logs',
        verbose_name=_("Visitor")
    )
    action = models.CharField(
        max_length=20,
        choices=Action.choices,
        verbose_name=_("Action")
    )
    details = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Details")
    )
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name=_("Performed By")
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Timestamp")
    )

    class Meta:
        verbose_name = _("Visitor Log")
        verbose_name_plural = _("Visitor Logs")
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.visitor} - {self.get_action_display()} @ {self.timestamp}"


class FormField(models.Model):
    """Model representing a form field for visitor registration"""
    class FieldType(models.TextChoices):
        TEXT = 'text', _('Text')
        NUMBER = 'number', _('Number')
        EMAIL = 'email', _('Email')
        PHONE = 'phone', _('Phone')
        DATE = 'date', _('Date')
        DATETIME = 'datetime', _('Date/Time')
        SELECT = 'select', _('Dropdown Select')
        CHECKBOX = 'checkbox', _('Checkbox')
        RADIO = 'radio', _('Radio Buttons')
        FILE = 'file', _('File Upload')
        TEXTAREA = 'textarea', _('Text Area')

    name = models.SlugField(
        max_length=100,
        unique=True,
        verbose_name=_("Field Name")
    )
    label = models.CharField(
        max_length=200,
        verbose_name=_("Display Label")
    )
    field_type = models.CharField(
        max_length=20,
        choices=FieldType.choices,
        default=FieldType.TEXT,
        verbose_name=_("Field Type")
    )
    required = models.BooleanField(
        default=False,
        verbose_name=_("Required Field")
    )
    order = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Display Order")
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Active")
    )
    options = models.TextField(
        blank=True,
        null=True,
        help_text=_("Comma-separated options for select/radio/checkbox"),
        verbose_name=_("Options")
    )
    placeholder = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name=_("Placeholder")
    )
    help_text = models.CharField(
        max_length=300,
        blank=True,
        null=True,
        verbose_name=_("Help Text")
    )
    visitor_type = models.CharField(
        max_length=20,
        choices=Visitor.VisitorType.choices,
        blank=True,
        null=True,
        verbose_name=_("Visitor Type Restriction")
    )

    class Meta:
        verbose_name = _("Form Field")
        verbose_name_plural = _("Form Fields")
        ordering = ['order', 'label']

    def __str__(self):
        return f"{self.label} ({self.get_field_type_display()})"


class Blacklist(models.Model):
    """Model representing a blacklisted visitor"""
    visitor = models.OneToOneField(
        Visitor,
        on_delete=models.CASCADE,
        related_name='blacklist_entry',
        verbose_name=_("Visitor")
    )
    reason = models.TextField(
        verbose_name=_("Blacklist Reason")
    )
    added_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name=_("Added By")
    )
    added_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Date Added")
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Active")
    )
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Notes")
    )

    class Meta:
        verbose_name = _("Blacklisted Visitor")
        verbose_name_plural = _("Blacklisted Visitors")
        ordering = ['-added_at']

    def __str__(self):
        return f"{self.visitor} ({_('Blacklisted')})"


class VisitorSetting(models.Model):
    """Model for visitor management settings"""
    require_photo = models.BooleanField(
        default=True,
        verbose_name=_("Require Visitor Photo")
    )
    require_id = models.BooleanField(
        default=False,
        verbose_name=_("Require ID Verification")
    )
    default_checkin_duration = models.PositiveIntegerField(
        default=4,
        verbose_name=_("Default Check-in Duration (hours)")
    )
    enable_pre_registration = models.BooleanField(
        default=True,
        verbose_name=_("Enable Pre-Registration")
    )
    enable_health_check = models.BooleanField(
        default=True,
        verbose_name=_("Enable Health Declaration")
    )
    enable_auto_checkout = models.BooleanField(
        default=True,
        verbose_name=_("Enable Auto Check-out")
    )
    auto_checkout_time = models.TimeField(
        default="18:00",
        verbose_name=_("Auto Check-out Time")
    )
    badge_template = models.FileField(
        upload_to='badge_templates/',
        blank=True,
        null=True,
        verbose_name=_("Badge Template File")
    )

    class Meta:
        verbose_name = _("Visitor Setting")
        verbose_name_plural = _("Visitor Settings")

    def __str__(self):
        return str(_("Visitor Management Settings"))

    def save(self, *args, **kwargs):
        self.pk = 1  # ensure singleton
        super().save(*args, **kwargs)

    @staticmethod
    def get_active_template():
        setting = VisitorSetting.objects.first()
        if setting and setting.badge_template:
            return setting.badge_template.path
        return None


class UserProfile(models.Model):
    """Model for user profile information"""
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="profile",
        verbose_name=_("User")
    )
    company = models.CharField(
        max_length=255,
        verbose_name=_("Company")
    )
    phone = models.CharField(
        max_length=20,
        verbose_name=_("Phone Number")
    )

    class Meta:
        verbose_name = _("User Profile")
        verbose_name_plural = _("User Profiles")

    def __str__(self):
        return self.user.get_full_name()
    

class Notification(models.Model):
    staff = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="visitor_staff_notifications"
    )
    visitor = models.ForeignKey(
        Visitor,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="visitor_visitor_notifications"
    )
class VisitorType(models.TextChoices):
    GUEST = 'guest', _('Guest')
    CONTRACTOR = 'contractor', _('Contractor')
    VENDOR = 'vendor', _('Vendor')
    INTERVIEW = 'interview', _('Interviewee')
    DELIVERY = 'delivery', _('Delivery')
    WALK_IN = 'walk_in', _('Walk-in')  # New
    PRE_REGISTERED = 'pre_registered', _('Pre-Registered')  # New
    
    


