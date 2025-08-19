# backend/visitors/views/landing.py
from rest_framework import views
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.utils.timezone import now
from django.db.models import Count, Avg, ExpressionWrapper, DurationField, F
from django.db.models.functions import TruncMonth, ExtractHour
from ..models import Visitor, VisitorLog
from ..serializers import VisitorSerializer
import logging

logger = logging.getLogger(__name__)

class LandingStatsView(views.APIView):
    """
    API endpoint for public landing page statistics.
    Provides key metrics about visitor activity that can be displayed publicly.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        """
        Returns aggregated statistics about visitor activity:
        - Total visits count
        - Today's check-ins
        - Average visit duration
        - System uptime
        - Trusted companies count
        - Support availability
        - Monthly visitor trends
        - Peak hours analysis
        """
        try:
            # Basic counts
            total_visits = self._get_total_visits()
            today_checkins = self._get_todays_checkins()
            trusted_companies = self._get_trusted_companies_count()
            current_visitors = self._get_current_visitors()

            # Calculated metrics
            avg_duration = self._calculate_average_duration()
            monthly_trends = self._get_monthly_trends()
            peak_hours = self._get_peak_hours()

            return Response({
                "uptime": self._get_system_uptime(),
                "avg_checkin_time": avg_duration,
                "trusted_companies": trusted_companies,
                "support": "24/7",
                "total_visits": total_visits,
                "today_checkins": today_checkins,
                "current_visitors": current_visitors,
                "monthly_trends": monthly_trends,
                "peak_hours": peak_hours,
                "last_updated": now().isoformat()
            })
        except Exception as e:
            logger.error(f"Error generating landing stats: {str(e)}", exc_info=True)
            return Response(
                {"error": "Could not generate statistics"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _get_total_visits(self):
        """Returns total number of visitor check-ins"""
        return Visitor.objects.count()

    def _get_todays_checkins(self):
        """Returns count of today's check-ins"""
        return Visitor.objects.filter(
            check_in_time__date=now().date()
        ).count()

    def _get_current_visitors(self):
        """Returns count of currently checked-in visitors"""
        return Visitor.objects.filter(
            status__in=['checked_in', 'in_meeting']
        ).count()

    def _calculate_average_duration(self):
        """
        Calculates average visit duration in hours and minutes format.
        Returns string like "1h 23m" or "<1m" if no data.
        """
        durations = Visitor.objects.exclude(
            check_out_time__isnull=True
        ).annotate(
            duration=ExpressionWrapper(
                F('check_out_time') - F('check_in_time'),
                output_field=DurationField()
            )
        )

        if not durations.exists():
            return "<1m"

        avg_seconds = durations.aggregate(
            avg=Avg('duration')
        )['avg'].total_seconds()

        hours = int(avg_seconds // 3600)
        minutes = int((avg_seconds % 3600) // 60)

        return f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"

    def _get_trusted_companies_count(self):
        """
        Returns count of unique companies that have visited.
        Enhanced with active company filtering.
        """
        return Visitor.objects.exclude(
            company__isnull=True
        ).exclude(
            company__exact=''
        ).values('company').distinct().count()

    def _get_system_uptime(self):
        """
        Returns system uptime percentage.
        In a real implementation, this would query monitoring systems.
        """
        return "99.9%"

    def _get_monthly_trends(self):
        """
        Returns visitor count by month for the last 12 months.
        Used for showing growth trends on landing page.
        """
        monthly_data = (
            Visitor.objects
            .annotate(month=TruncMonth('check_in_time'))
            .values('month')
            .annotate(count=Count('id'))
            .order_by('-month')[:12]  # Last 12 months
        )
        return [
            {
                'month': item['month'].strftime('%Y-%m'),
                'count': item['count'],
                'growth_rate': self._calculate_growth_rate(monthly_data, item)
            }
            for item in monthly_data
        ]

    def _get_peak_hours(self):
        """
        Returns visitor distribution by hour of day.
        Helps identify busiest times.
        """
        return (
            Visitor.objects
            .annotate(hour=ExtractHour('check_in_time'))
            .values('hour')
            .annotate(count=Count('id'))
            .order_by('hour')
        )

    def _calculate_growth_rate(self, monthly_data, current_item):
        """
        Helper method to calculate month-over-month growth rate.
        """
        try:
            current_index = list(monthly_data).index(current_item)
            if current_index + 1 < len(monthly_data):
                previous_count = monthly_data[current_index + 1]['count']
                if previous_count > 0:
                    return round(
                        (current_item['count'] - previous_count) / previous_count * 100, 
                        1
                    )
        except (ValueError, IndexError):
            pass
        return 0