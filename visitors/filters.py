import django_filters
from .models import Visitor
from .models import VisitorLog

class VisitorLogFilter(django_filters.FilterSet):
    start_date = django_filters.DateFilter(field_name='timestamp', lookup_expr='gte')
    end_date = django_filters.DateFilter(field_name='timestamp', lookup_expr='lte')
    action = django_filters.CharFilter(field_name='action', lookup_expr='iexact')
    user_email = django_filters.CharFilter(field_name='user__email', lookup_expr='icontains')
    visitor_name = django_filters.CharFilter(field_name='visitor__full_name', lookup_expr='icontains')

    class Meta:
        model = VisitorLog
        fields = ['start_date', 'end_date', 'action', 'user_email', 'visitor_name']

class VisitorFilter(django_filters.FilterSet):
    host_name = django_filters.CharFilter(method='filter_by_host_name')

    class Meta:
        model = Visitor
        fields = ['status', 'check_in_time', 'host_name']

    def filter_by_host_name(self, queryset, name, value):
        return queryset.filter(
            models.Q(host__first_name__icontains=value) | 
            models.Q(host__last_name__icontains=value)
        )
