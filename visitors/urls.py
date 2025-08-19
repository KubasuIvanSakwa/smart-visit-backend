from django.urls import path, include
from rest_framework.routers import DefaultRouter
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from .views.visitors import(
    VisitorViewSet,
    ExportVisitorsCSVView,
    VisitorDetailView,
    VisitorBadgePDFView,
    QRCheckInAPIView,
    EmergencyReportAPIView,
    EmergencyReportPDFView,
    DashboardStatsView,
    CurrentVisitorsView,
    PeakHoursView,
    MonthlyTrendsView,
    PendingApprovalsView,
    VisitorStatsView,
    VisitorReportsAPIView
    
)
from visitors.views.visitors import VisitorViewSet
from .views.forms import (
    FormFieldViewSet)
from .views.logs import (VisitorLogListView)
from .views.landing import (LandingStatsView)


from authentication.views import (
    CustomTokenObtainPairView as LoginView,
    RegisterView,
    LogoutView,
    VerifyTokenView,
    RefreshTokenView,
    PasswordResetView,
    PasswordChangeView
)

from notifications.notifier import (
    ManualNotificationView,
    NotificationViewSet,
    NotifyVisitorView,
    SubscribeToNotificationsView,
    NotificationPreferencesView,
    NotificationListView
)

from visitors.views.visitors import kiosk_checkin_view, offline_checkin_view



# Debug views
def debug_view(request):
    return JsonResponse({"debug": "success", "path": "api/debug-test/"})

def debug_urls(request):
    from django.urls import get_resolver
    urls = []
    for url_pattern in get_resolver().url_patterns:
        urls.append(str(url_pattern.pattern))
    return JsonResponse({'available_urls': urls})

# Initialize DefaultRouter
router = DefaultRouter()
router.register(r'visitors', VisitorViewSet, basename='visitors')
router.register(r'form-fields', FormFieldViewSet, basename='form-fields')
router.register(r'notifications', NotificationViewSet, basename='notifications')


# API URL Patterns
api_urlpatterns = [
    # Debug endpoints (accessible at /api/debug-test/ and /api/debug-urls/)
    path('debug-test/', debug_view),
    path('debug-urls/', debug_urls),
   
    path('api/', include(router.urls)),


    # 🔁 Router URLs
    path('', include(router.urls)),
    
    # 🛂 Visitor Management
    path('visitors/', include([
        path('logs/', VisitorLogListView.as_view(), name='visitor-logs'),
        path('checkin/', kiosk_checkin_view, name='visitor-checkin'),  # Use kiosk_checkin_view here
        path('qr-checkin/', QRCheckInAPIView.as_view(), name='qr-checkin'),
        path('kiosk-checkin/', kiosk_checkin_view, name='kiosk-checkin'),
        path('offline-checkin/', offline_checkin_view, name='offline-checkin'),
        path('<int:id>/detail/', VisitorDetailView.as_view(), name='visitor-detail'),
        path('<int:id>/badge/', VisitorBadgePDFView.as_view(), name='visitor-badge'),
        path('emergency/report/pdf/', EmergencyReportPDFView.as_view(), name='emergency-report-pdf'),
        path('analytics/', VisitorReportsAPIView.as_view(), name='visitor-reports-analytics'),
    ])),

    # 📊 Dashboard Endpoints
    path('dashboard/', include([
        path('stats/', DashboardStatsView.as_view(), name='dashboard-stats'),  # Fixed duplicate 'dashboard' prefix
        path('current-visitors/', CurrentVisitorsView.as_view(), name='current-visitors'),
        path('pending-approvals/', PendingApprovalsView.as_view(), name='pending-approvals'),
        path('peak-hours/', PeakHoursView.as_view(), name='peak-hours'),
        path('monthly-trends/', MonthlyTrendsView.as_view(), name='monthly-trends'),
    ])),

    # 📈 Analytics & Reporting
    path('analytics/', include([
        path('', VisitorStatsView.as_view(), name='visitor-stats'),
        path('landing/', LandingStatsView.as_view(), name='landing-stats'),
        path('export/csv/', ExportVisitorsCSVView.as_view(), name='visitor-export'),
       
    ])),

    # 🚨 Emergency Features
    path('emergency/', include([
        path('report/', EmergencyReportAPIView.as_view(), name='emergency-report'),
        path('report/pdf/', EmergencyReportPDFView.as_view(), name='emergency-report-pdf'),
    ])),

    # 🔔 Notification System
    path('notifications/', include([
        path('subscribe/', SubscribeToNotificationsView.as_view(), name='notification-subscribe'),
        path('preferences/', NotificationPreferencesView.as_view(), name='notification-preferences'),
        path('visitor/', NotifyVisitorView.as_view(), name='notify-visitor'),
        path('manual/', ManualNotificationView.as_view(), name='manual-notification'),
        path('notifications/', NotificationListView.as_view(), name='notification-list'),
    ])),
]

# Base URL Patterns
urlpatterns = [
    path('', include(api_urlpatterns)),  # Changed from path('api/', ...) to avoid duplicate prefix
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Optional: API versioning prefix
if hasattr(settings, 'API_VERSION_PREFIX'):
    urlpatterns = [
        path(f'{settings.API_VERSION_PREFIX}/', include(urlpatterns))
    ] 