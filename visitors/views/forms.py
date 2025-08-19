# backend/visitors/views/form_fields.py
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from ..models import FormField
from ..serializers import FormFieldSerializer
from ..permissions import IsAdminUser, IsReceptionistUser

class FormFieldViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing form fields.
    Allows CRUD operations on form fields and additional actions for managing active fields and ordering.
    """
    queryset = FormField.objects.all().order_by('order')
    serializer_class = FormFieldSerializer
    permission_classes = [IsAuthenticated, IsAdminUser | IsReceptionistUser]
    
    @action(detail=False, methods=['get'])
    def active_fields(self, request):
        """
        Returns only active form fields.
        Used by the frontend to display only relevant fields in the visitor form.
        """
        fields = self.get_queryset().filter(is_active=True)
        serializer = self.get_serializer(fields, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def update_order(self, request):
        """
        Updates the order of form fields based on the provided list.
        Expects a list of objects with 'id' and 'order' properties.
        """
        try:
            with transaction.atomic():
                for item in request.data:
                    field = FormField.objects.get(id=item['id'])
                    field.order = item['order']
                    field.save()
            return Response({'message': 'Order updated successfully'})
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    def perform_create(self, serializer):
        """
        Custom create handler to ensure proper field ordering.
        """
        last_order = FormField.objects.order_by('-order').first()
        new_order = (last_order.order + 1) if last_order else 0
        serializer.save(order=new_order)

    def perform_destroy(self, instance):
        """
        Custom delete handler to maintain data consistency.
        """
        with transaction.atomic():
            # Reorder remaining fields after deletion
            instance.delete()
            fields = FormField.objects.filter(order__gt=instance.order)
            fields.update(order=F('order') - 1)