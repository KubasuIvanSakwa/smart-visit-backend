# backend/visitors/views/analytics.py
from rest_framework import views
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser 
from django.utils.timezone import now
from django.http import HttpResponse
from django.db.models import Count, F, ExpressionWrapper, DurationField, Avg
from django.db.models.functions import TruncMonth, ExtractHour
from django.db import transaction
from django.http import HttpResponse
from django.utils.timezone import now, timedelta
from django.db.models import Count
import csv
from visitors.models import Visitor

from rest_framework.views import APIView
# If your class is actually called MonthlyVisitorTrendsView
import csv
from reportlab.pdfgen import canvas
from io import BytesIO

from ..models import Visitor
from ..serializers import EmergencyVisitorSerializer


class VisitorAnalyticsBaseView(views.APIView):
    """Base view for visitor analytics with common helper methods"""
    permission_classes = [IsAuthenticated]

    def _get_date_filters(self):
        """Returns common date filters used across analytics"""
        return {
            'today': now().date(),
            'this_month': now().month,
            'this_year': now().year
        }


class VisitorStatsView(VisitorAnalyticsBaseView):
    """
    API endpoint for comprehensive visitor statistics
    GET /api/analytics/stats/
    """
    def get(self, request):
        dates = self._get_date_filters()
        
        stats = {
            "current_visitors": self._get_current_visitors(),
            "todays_checkins": self._get_todays_checkins(dates['today']),
            "monthly_total": self._get_monthly_total(dates['this_month']),
            "average_duration": self._get_average_duration(),
            "visitor_types": self._get_visitor_type_stats(dates['this_year'])
        }
        return Response(stats)

    def _get_current_visitors(self):
        return Visitor.objects.exclude(status='checked_out').count()

    def _get_todays_checkins(self, today):
        return Visitor.objects.filter(check_in_time__date=today).count()

    def _get_monthly_total(self, month):
        return Visitor.objects.filter(check_in_time__month=month).count()

    def _get_average_duration(self):
        durations = Visitor.objects.exclude(check_out_time=None).annotate(
            duration=ExpressionWrapper(
                F('check_out_time') - F('check_in_time'),
                output_field=DurationField()
            )
        )
        
        if durations.exists():
            avg_seconds = durations.aggregate(avg=Avg('duration'))['avg'].total_seconds()
            hours = int(avg_seconds // 3600)
            mins = int((avg_seconds % 3600) // 60)
            return f"{hours}h {mins}m"
        return "0h 0m"

    def _get_visitor_type_stats(self, year):
        return (Visitor.objects
                .filter(check_in_time__year=year)
                .values('visitor_type')
                .annotate(count=Count('id'))
                .order_by('-count'))


class VisitorTrendsView(VisitorAnalyticsBaseView):
    """
    API endpoint for visitor trend analysis
    GET /api/analytics/trends/
    """
    def get(self, request):
        dates = self._get_date_filters()
        
        trends = {
            "peak_hours": self._get_peak_hours(),
            "monthly_trends": self._get_monthly_trends(),
            "yearly_comparison": self._get_yearly_comparison(dates['this_year'])
        }
        return Response(trends)

    def _get_peak_hours(self):
        return (Visitor.objects
                .annotate(hour=ExtractHour('check_in_time'))
                .values('hour')
                .annotate(count=Count('id'))
                .order_by('hour'))

    def _get_monthly_trends(self):
        return (Visitor.objects
                .annotate(month=TruncMonth('check_in_time'))
                .values('month')
                .annotate(count=Count('id'))
                .order_by('month'))

    def _get_yearly_comparison(self, current_year):
        # Compare with previous year
        previous_year = current_year - 1
        current_data = (Visitor.objects
                       .filter(check_in_time__year=current_year)
                       .count())
        previous_data = (Visitor.objects
                        .filter(check_in_time__year=previous_year)
                        .count())
        
        return {
            'current_year': current_year,
            'current_count': current_data,
            'previous_year': previous_year,
            'previous_count': previous_data,
            'growth': current_data - previous_data if previous_data else 0
        }


class ExportVisitorsView(VisitorAnalyticsBaseView):
    """
    API endpoint for exporting visitor data
    GET /api/analytics/export/
    """
    def get(self, request, format='csv'):
        if format == 'csv':
            return self._export_csv()
        elif format == 'pdf':
            return self._export_pdf()
        return Response(
            {"error": "Unsupported format"}, 
            status=400
        )

    def _export_csv(self):
        visitors = (Visitor.objects
                   .all()
                   .select_related('host')
                   .order_by('-check_in_time'))
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="visitors_export.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Name', 'Company', 'Email', 'Phone',
            'Host', 'Visitor Type',
            'Check-in Time', 'Check-out Time', 'Status',
            'Purpose', 'Notes'
        ])
        
        for visitor in visitors:
            writer.writerow([
                visitor.full_name,
                visitor.company,
                visitor.email or '',
                visitor.phone or '',
                visitor.host.get_full_name() if visitor.host else '',
                visitor.visitor_type,
                visitor.check_in_time.strftime('%Y-%m-%d %H:%M'),
                visitor.check_out_time.strftime('%Y-%m-%d %H:%M') if visitor.check_out_time else '',
                visitor.status,
                visitor.purpose or '',
                visitor.notes or ''
            ])
        
        return response

    def _export_pdf(self):
        visitors = Visitor.objects.filter(status__in=['checked_in', 'in_meeting'])
        
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="visitors_report.pdf"'
        
        p = canvas.Canvas(response)
        y = 800
        
        # Header
        p.setFont("Helvetica-Bold", 16)
        p.drawString(100, y, "Visitors Report")
        y -= 40
        
        # Visitor List
        p.setFont("Helvetica", 10)
        for visitor in visitors:
            text = (f"{visitor.full_name} | {visitor.phone} | "
                   f"{visitor.company} | Badge: {visitor.badge_number or 'N/A'}")
            p.drawString(50, y, text)
            y -= 20
            
            if y < 50:  # New page if running out of space
                p.showPage()
                y = 800
                p.setFont("Helvetica", 10)
        
        p.save()
        return response


class EmergencyReportView(VisitorAnalyticsBaseView):
    """
    API endpoint for emergency reports (admin only)
    GET /api/analytics/emergency/
    """
    permission_classes = [IsAdminUser ]

    def get(self, request):
        visitors = Visitor.objects.filter(status__in=['checked_in', 'in_meeting'])
        serializer = EmergencyVisitorSerializer(visitors, many=True)
        return Response({
            'count': visitors.count(),
            'visitors': serializer.data
        })

class ExportVisitorsCSVView(APIView):
    def get(self, request, *args, **kwargs):
        response = HttpResponse(
            content_type='text/csv',
            headers={'Content-Disposition': 'attachment; filename="visitors.csv"'},
        )

        writer = csv.writer(response)
        writer.writerow(['Name', 'Phone', 'Check In Time', 'Branch'])

        for visitor in Visitor.objects.all():
            writer.writerow([
                visitor.name,
                visitor.phone_number,
                visitor.check_in_time,
                visitor.branch.name if visitor.branch else ''
            ])

        return response

class PeakHoursView(APIView):
    def get(self, request):
        # Group by hour and count number of check-ins
        from django.db.models.functions import ExtractHour
        from django.db.models import Count

        data = (
            Visitor.objects.annotate(hour=ExtractHour('check_in_time'))
            .values('hour')
            .annotate(count=Count('id'))
            .order_by('hour')
        )

        return Response(data)

class MonthlyTrendsView(APIView):
    def get(self, request):
        data = (
            Visitor.objects.annotate(month=TruncMonth('check_in_time'))
            .values('month')
            .annotate(count=Count('id'))
            .order_by('month')
        )
        return Response(data)