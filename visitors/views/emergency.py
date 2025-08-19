# backend/visitors/views/emergency.py
from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from rest_framework.decorators import action
from django.http import HttpResponse, JsonResponse
from django.db.models import Q
from django.utils.timezone import now
from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, 
    Paragraph, 
    Table, 
    TableStyle, 
    Spacer,
    Image
)
from io import BytesIO
import qrcode
import logging

from ..models import Visitor, VisitorLog, CustomUser
from ..serializers import EmergencyVisitorSerializer
from notifications.notifier import  (
    send_email_notification,
    send_sms_notification,
    trigger_host_notification
)

logger = logging.getLogger(__name__)


class EmergencyBaseView(views.APIView):
    """Base view for emergency-related endpoints with common functionality"""
    permission_classes = [IsAdminUser]
    
    def _get_current_visitors(self):
        """Returns queryset of visitors currently in the building"""
        return Visitor.objects.filter(
            Q(status='checked_in') | Q(status='in_meeting')
        ).select_related('host', 'location').prefetch_related('custom_fields')
    
    def _create_emergency_log(self, action, details, user):
        """Creates an audit log entry for emergency actions"""
        VisitorLog.objects.create(
            action=action,
            details=details,
            user=user
        )


class EmergencyReportAPIView(EmergencyBaseView):
    """
    API endpoint for emergency visitor reporting
    
    GET /api/emergency/report/
    - Returns JSON with all current visitors and emergency contacts
    - Includes visitor details, host information, and location data
    - Generates audit log entry
    
    Permissions: Admin only
    """
    
    def get(self, request):
        try:
            visitors = self._get_current_visitors().order_by('-check_in_time')
            serializer = EmergencyVisitorSerializer(visitors, many=True)
            
            self._create_emergency_log(
                action='EMERGENCY_REPORT_GENERATED',
                details=f'Emergency report generated with {visitors.count()} visitors',
                user=request.user
            )
            
            response_data = {
                'timestamp': now().isoformat(),
                'total_visitors': visitors.count(),
                'visitors': serializer.data,
                'emergency_contacts': self._get_emergency_contacts(),
                'building_status': self._get_building_status(),
                'assembly_points': self._get_assembly_points()
            }
            
            return Response(response_data)
            
        except Exception as e:
            logger.error(f"Emergency report error: {str(e)}")
            return Response(
                {"error": "Failed to generate emergency report"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _get_emergency_contacts(self):
        """Returns emergency contact information from settings"""
        return {
            'security': getattr(settings, 'EMERGENCY_SECURITY_NUMBER', '+1-555-123-4567'),
            'fire_department': getattr(settings, 'EMERGENCY_FIRE_NUMBER', '+1-555-987-6543'),
            'medical': getattr(settings, 'EMERGENCY_MEDICAL_NUMBER', '+1-555-789-0123'),
            'facility_manager': getattr(settings, 'EMERGENCY_MANAGER_EMAIL', 'facility@example.com'),
            'floor_wardens': self._get_floor_wardens()
        }
    
    def _get_floor_wardens(self):
        """Returns floor-specific emergency contacts"""
        return [
            {'floor': 'Ground', 'name': 'John Smith', 'phone': 'x1234'},
            {'floor': '1st', 'name': 'Sarah Lee', 'phone': 'x5678'},
            {'floor': '2nd', 'name': 'Mike Johnson', 'phone': 'x9012'}
        ]
    
    def _get_building_status(self):
        """Returns current building status information"""
        return {
            'last_drill': getattr(settings, 'LAST_SAFETY_DRILL', '2023-11-15'),
            'evacuation_routes_updated': True,
            'elevators_disabled': False,
            'fire_alarm_active': False
        }
    
    def _get_assembly_points(self):
        """Returns designated emergency assembly points"""
        return [
            {'name': 'North Parking Lot', 'capacity': 200, 'accessibility': True},
            {'name': 'South Lawn', 'capacity': 150, 'accessibility': True},
            {'name': 'East Courtyard', 'capacity': 100, 'accessibility': False}
        ]


class EmergencyReportPDFView(EmergencyBaseView):
    """
    Generates a printable PDF emergency report
    
    GET /api/emergency/report/pdf/
    - Returns PDF document with:
      - Emergency procedures
      - Visitor listing with photos/QR codes
      - Contact information
      - Building maps/exit routes
    - Generates audit log entry
    
    Permissions: Admin only
    """
    
    def get(self, request):
        try:
            visitors = self._get_current_visitors()
            buffer = BytesIO()
            
            doc = SimpleDocTemplate(
                buffer,
                pagesize=letter,
                title="Emergency Visitor Report",
                author="Visitor Management System"
            )
            
            elements = []
            
            # Add report header
            styles = self._get_pdf_styles()
            elements.append(Paragraph("EMERGENCY VISITOR REPORT", styles['Title']))
            elements.append(Paragraph(f"Generated: {now().strftime('%Y-%m-%d %H:%M')}", styles['Small']))
            elements.append(Paragraph(f"Total Visitors: {visitors.count()}", styles['Small']))
            elements.append(Spacer(1, 24))
            
            # Add emergency procedures
            elements.append(Paragraph("EMERGENCY PROCEDURES", styles['Heading2']))
            procedures = [
                "1. Remain calm and follow evacuation routes",
                "2. Assist visitors as needed",
                "3. Account for all personnel at assembly points",
                "4. Do not use elevators",
                "5. Report to floor warden if present"
            ]
            for procedure in procedures:
                elements.append(Paragraph(procedure, styles['Normal']))
            elements.append(Spacer(1, 24))
            
            # Add emergency contacts table
            elements.append(Paragraph("EMERGENCY CONTACTS", styles['Heading2']))
            contacts = [
                ["Security", settings.EMERGENCY_SECURITY_NUMBER],
                ["Fire Department", settings.EMERGENCY_FIRE_NUMBER],
                ["Medical", settings.EMERGENCY_MEDICAL_NUMBER],
                ["Facility Manager", settings.EMERGENCY_MANAGER_EMAIL]
            ]
            contact_table = Table(contacts, colWidths=[150, 150])
            contact_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOX', (0, 0), (-1, -1), 1, colors.black),
            ]))
            elements.append(contact_table)
            elements.append(Spacer(1, 24))
            
            # Add visitor table
            elements.append(Paragraph("CURRENT VISITORS", styles['Heading2']))
            visitor_data = self._prepare_visitor_data(visitors)
            visitor_table = Table(
                visitor_data, 
                colWidths=[100, 80, 80, 80, 60, 60],
                repeatRows=1
            )
            visitor_table.setStyle(self._get_table_style())
            elements.append(visitor_table)
            
            # Build PDF document
            doc.build(elements)
            
            # Create log entry
            self._create_emergency_log(
                action='EMERGENCY_PDF_GENERATED',
                details=f'Generated PDF report with {visitors.count()} visitors',
                user=request.user
            )
            
            # Return PDF response
            buffer.seek(0)
            response = HttpResponse(buffer, content_type='application/pdf')
            response['Content-Disposition'] = 'attachment; filename="emergency_visitor_report.pdf"'
            return response
            
        except Exception as e:
            logger.error(f"PDF generation error: {str(e)}")
            return Response(
                {"error": "Failed to generate PDF report"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _get_pdf_styles(self):
        """Returns configured PDF styles"""
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(
            name='Title',
            fontSize=16,
            leading=20,
            alignment=1,  # Center aligned
            fontName='Helvetica-Bold'
        ))
        styles.add(ParagraphStyle(
            name='Heading2',
            fontSize=12,
            leading=15,
            fontName='Helvetica-Bold',
            spaceAfter=6
        ))
        return styles
    
    def _prepare_visitor_data(self, visitors):
        """Prepares visitor data for PDF table"""
        visitor_data = [
            ["Name", "Company", "Host", "Location", "Check-In", "Badge #"]
        ]
        
        for visitor in visitors:
            visitor_data.append([
                visitor.full_name,
                visitor.company or "N/A",
                visitor.host.get_full_name() if visitor.host else "N/A",
                getattr(visitor.location, 'name', 'Main Lobby'),
                visitor.check_in_time.strftime('%H:%M'),
                visitor.badge_number or "N/A"
            ])
        
        return visitor_data
    
    def _get_table_style(self):
        """Returns table styling configuration"""
        return TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#003366')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ])


class EmergencyNotificationView(EmergencyBaseView):
    """
    Emergency notification system
    
    POST /api/emergency/notify/
    - Sends alerts to all hosts with current visitors
    - Supports email, SMS, and real-time notifications
    - Tracks notification delivery
    
    Request Body:
    {
        "message": "Emergency evacuation required",
        "type": "evacuation",
        "channels": ["email", "sms", "push"]
    }
    
    Permissions: Admin only
    """
    
    def post(self, request):
        try:
            message = request.data.get(
                'message', 
                'EMERGENCY: Please proceed to the nearest exit immediately'
            )
            emergency_type = request.data.get('type', 'evacuation').lower()
            channels = request.data.get('channels', ['email', 'push'])
            
            if not isinstance(channels, list):
                return Response(
                    {"error": "Channels must be a list"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get unique hosts with current visitors
            visitors = self._get_current_visitors()
            hosts = {
                visitor.host for visitor in visitors 
                if visitor.host and visitor.host.is_active
            }
            
            notification_results = {
                'total_hosts': len(hosts),
                'successful': 0,
                'failed': 0,
                'details': []
            }
            
            for host in hosts:
                try:
                    result = self._notify_host(host, message, emergency_type, channels)
                    notification_results['details'].append({
                        'host_id': host.id,
                        'host_email': host.email,
                        'status': 'success',
                        'channels': result
                    })
                    notification_results['successful'] += 1
                except Exception as e:
                    notification_results['details'].append({
                        'host_id': host.id,
                        'host_email': host.email,
                        'status': 'failed',
                        'error': str(e)
                    })
                    notification_results['failed'] += 1
                    logger.error(f"Failed to notify host {host.id}: {str(e)}")
            
            # Log the notification event
            self._create_emergency_log(
                action='EMERGENCY_NOTIFICATION_SENT',
                details=(
                    f'Sent {emergency_type} alert via {channels} to '
                    f'{notification_results["successful"]}/{len(hosts)} hosts'
                ),
                user=request.user
            )
            
            return Response({
                'status': 'completed',
                'results': notification_results,
                'emergency_type': emergency_type,
                'timestamp': now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Emergency notification error: {str(e)}")
            return Response(
                {"error": "Failed to send emergency notifications"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _notify_host(self, host, message, emergency_type, channels):
        """Sends notifications to a host through specified channels"""
        results = {}
        
        # Prepare common notification data
        notification_data = {
            "type": emergency_type,
            "message": message,
            "timestamp": now().isoformat(),
            "host_id": host.id
        }
        
        # Send via requested channels
        if 'email' in channels:
            results['email'] = self._send_email_notification(host, message, emergency_type)
        
        if 'sms' in channels and host.phone:
            results['sms'] = self._send_sms_notification(host, message)
        
        if 'push' in channels:
            results['push'] = self._send_push_notification(host, notification_data)
        
        return results
    
    def _send_email_notification(self, host, message, emergency_type):
        """Sends emergency email notification"""
        subject = f"EMERGENCY: {emergency_type.upper()} ALERT"
        email_message = f"""
        EMERGENCY NOTIFICATION
        Type: {emergency_type.upper()}
        Time: {now().strftime('%Y-%m-%d %H:%M')}
        
        {message}
        
        Please follow established emergency procedures.
        Do not reply to this automated message.
        """
        
        return send_email_notification(
            subject=subject,
            message=email_message,
            recipient=host.email,
            priority='high'
        )
    
    def _send_sms_notification(self, host, message):
        """Sends emergency SMS notification"""
        sms_message = f"EMERGENCY: {message[:140]}"  # Truncate to SMS length
        
        return send_sms_notification(
            phone_number=host.phone,
            message=sms_message
        )
    
    def _send_push_notification(self, host, data):
        """Sends real-time push notification"""
        return trigger_host_notification(
            channel=f"user_{host.id}",
            event="emergency_alert",
            data=data
        )


class EmergencyChecklistView(EmergencyBaseView):
    """
    Provides emergency preparedness checklist and resources
    
    GET /api/emergency/checklist/
    - Returns emergency procedures
    - Building-specific safety information
    - Evacuation routes and assembly points
    - Emergency contact list
    
    Permissions: Admin only
    """
    
    def get(self, request):
        try:
            return Response({
                'emergency_procedures': self._get_emergency_procedures(),
                'evacuation_routes': self._get_evacuation_routes(),
                'emergency_equipment': self._get_emergency_equipment(),
                'first_aid_locations': self._get_first_aid_locations(),
                'last_updated': getattr(settings, 'SAFETY_PLAN_UPDATED', '2023-01-01')
            })
        except Exception as e:
            logger.error(f"Checklist error: {str(e)}")
            return Response(
                {"error": "Failed to retrieve emergency checklist"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _get_emergency_procedures(self):
        """Returns standard emergency procedures"""
        return {
            'fire': {
                'steps': [
                    'Activate nearest fire alarm',
                    'Evacuate immediately',
                    'Use stairs, not elevators',
                    'Assemble at designated point'
                ],
                'additional_instructions': 'Close all doors behind you'
            },
            'earthquake': {
                'steps': [
                    'Drop, cover, and hold on',
                    'Stay indoors until shaking stops',
                    'Evacuate if building is unsafe',
                    'Watch for falling debris'
                ]
            },
            'medical': {
                'steps': [
                    'Call emergency medical services',
                    'Provide first aid if trained',
                    'Clear area if needed',
                    'Stay with injured person'
                ]
            }
        }
    
    def _get_evacuation_routes(self):
        """Returns building evacuation routes"""
        return {
            'ground_floor': {
                'primary': 'Main entrance doors',
                'secondary': 'Rear fire exit',
                'disabled_access': 'Ramp at northwest corner'
            },
            'upper_floors': {
                'primary': 'Central stairwell A',
                'secondary': 'East stairwell B',
                'disabled_access': 'Evacuation chairs in stairwells'
            }
        }
    
    def _get_emergency_equipment(self):
        """Returns locations of emergency equipment"""
        return [
            {'type': 'Fire extinguisher', 'location': 'Near elevators on each floor'},
            {'type': 'First aid kit', 'location': 'Reception and kitchen areas'},
            {'type': 'Emergency phone', 'location': 'Building entrances'},
            {'type': 'Defibrillator', 'location': 'Main lobby wall mount'}
        ]
    
    def _get_first_aid_locations(self):
        """Returns first aid station locations"""
        return [
            {'floor': 'Ground', 'location': 'Reception desk'},
            {'floor': '1st', 'location': 'North corridor near restrooms'},
            {'floor': '2nd', 'location': 'Break room wall mount'}
        ]