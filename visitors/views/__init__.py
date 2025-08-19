# visitors/views/__init__.py
from .visitors import (
    VisitorViewSet,
    kiosk_checkin_view,
    VisitorDetailView,
    CurrentVisitorsView,
    QRCheckInAPIView,
    kiosk_checkin_view,
    VisitorBadgePDFView,
    offline_checkin_view,
    DashboardStatsView,
    PendingApprovalsView
)

from .analytics import (
    VisitorStatsView,
    VisitorTrendsView,
    ExportVisitorsCSVView,
    MonthlyTrendsView,
    PeakHoursView,
    ExportVisitorsView
)

from .authentication import (
    LoginView,
    RegisterView
)

from .emergency import (
    EmergencyReportAPIView,
    EmergencyReportPDFView
)

from .forms import FormFieldViewSet
from .landing import LandingStatsView
from .logs import VisitorLogListView

from notifications.notifier import (
    ManualNotificationView,
    NotificationViewSet
)


__all__ = [
    # Visitor management
    'VisitorViewSet',
    kiosk_checkin_view,
    'VisitorDetailView',
    'CurrentVisitorsView',
    'QRCheckInAPIView',
    'kiosk_checkin_view',
    'VisitorBadgePDFView',
    'offline_checkin_view',
    'DashboardStatsView',
    'PendingApprovalsView',
    
    # Analytics
    'VisitorStatsView',
    'VisitorTrendsView',
    'ExportVisitorsCSVView',
    'MonthlyTrendsView',
    'PeakHoursView',
    'ExportVisitorsView',
    
    # Authentication
    'LoginView',
    'RegisterView',
    
    # Emergency
    'EmergencyReportAPIView',
    'EmergencyReportPDFView',
    
    # Forms
    'FormFieldViewSet',
    
    # Landing
    'LandingStatsView',
    
    # Logs
    'VisitorLogListView',
    
    # Notifications
    'ManualNotificationView',
    'NotificationViewSet'
]