# backend/visitors/views/logs.py
from rest_framework import generics, filters
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from ..models import VisitorLog
from ..serializers import VisitorLogSerializer
from ..filters import VisitorLogFilter
from rest_framework.pagination import PageNumberPagination
import logging

logger = logging.getLogger(__name__)

class VisitorLogPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100

class VisitorLogListView(generics.ListAPIView):
    """
    API endpoint that lists all visitor log entries with filtering and search capabilities.
    Allows filtering by:
    - Action type (check_in, check_out, etc.)
    - Date range
    - Visitor name
    - User who performed the action
    """
    serializer_class = VisitorLogSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = VisitorLogFilter
    pagination_class = VisitorLogPagination
    
    search_fields = [
        'visitor__full_name',
        'visitor__company',
        'action',
        'details',
        'user__email',
        'user__first_name',
        'user__last_name'
    ]
    
    ordering_fields = [
        'timestamp',
        'visitor__full_name',
        'action'
    ]
    
    ordering = ['-timestamp']  # Default ordering

    def get_queryset(self):
        """
        Returns filtered queryset of VisitorLog entries with select_related
        for performance optimization.
        """
        try:
            queryset = VisitorLog.objects.select_related(
                'visitor',
                'user'
            ).all()
            
            # Additional custom filtering can be added here if needed
            return queryset
            
        except Exception as e:
            logger.error(f"Error retrieving visitor logs: {str(e)}", exc_info=True)
            return VisitorLog.objects.none()

    def list(self, request, *args, **kwargs):
        """
        Override list method to add custom metadata to the response.
        """
        response = super().list(request, *args, **kwargs)
        
        # Add summary statistics to the response
        if response.data:
            try:
                queryset = self.filter_queryset(self.get_queryset())
                response.data['summary'] = {
                    'total_entries': queryset.count(),
                    'check_in_count': queryset.filter(action='check_in').count(),
                    'check_out_count': queryset.filter(action='check_out').count(),
                    'first_entry': queryset.last().timestamp if queryset.exists() else None,
                    'last_entry': queryset.first().timestamp if queryset.exists() else None
                }
            except Exception as e:
                logger.error(f"Error generating log summary: {str(e)}")
        
        return response