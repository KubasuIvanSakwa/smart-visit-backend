
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from rest_framework.generics import ListAPIView
from visitors.models import UserProfile
from .serializers import UserProfileSerializer
from django.contrib.auth import get_user_model
from .serializers import UserListSerializer
from rest_framework.generics import UpdateAPIView
from django.db import IntegrityError
from .serializers import (
    CustomTokenObtainPairSerializer,
    UserRegisterSerializer,
    PasswordResetSerializer
)
import logging

User = get_user_model()
logger = logging.getLogger(__name__)

class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Custom JWT token obtain view with extended user data
    """
    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == status.HTTP_200_OK:
            # Decode token to get user details
            access_token = AccessToken(response.data['access'])
            user = User.objects.get(id=access_token['user_id'])
            
            response.data.update({
                'user_id': user.id,
                'email': user.email,
                'role': user.role,
                'first_name': user.first_name,
                'last_name': user.last_name
            })
        return response

class VerifyTokenView(APIView):
    """
    Verify JWT token and return user data
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({
            'user_id': request.user.id,
            'email': request.user.email,
            'role': request.user.role,
            'first_name': request.user.first_name,
            'last_name': request.user.last_name
        }, status=status.HTTP_200_OK)

class LogoutView(APIView):
    """
    Blacklist refresh token to log user out
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            token = RefreshToken(refresh_token)
            token.blacklist()
            
            # Clear user session data if needed
            request.user.auth_token.delete()
            
            return Response(
                {'message': 'Successfully logged out'},
                status=status.HTTP_205_RESET_CONTENT
            )
        except Exception as e:
            logger.error(f"Logout error: {str(e)}")
            return Response(
                {'error': 'Invalid token or already logged out'},
                status=status.HTTP_400_BAD_REQUEST
            )

class RegisterView(APIView):
    def post(self, request):
        try:
            data = request.data
            
            # Validate required fields (removed username from required fields)
            required_fields = ['email', 'password', 'password2', 
                             'first_name', 'last_name', 'role']
            for field in required_fields:
                if field not in data:
                    return Response(
                        {'error': f'{field} is required'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # Check if passwords match
            if data['password'] != data['password2']:
                return Response(
                    {'error': 'Passwords do not match'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Check if user exists (only check email)
            if User.objects.filter(email=data['email']).exists():
                return Response(
                    {'error': 'Email already exists'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Create user without username
            user = User.objects.create_user(
                email=data['email'],
                password=data['password'],
                first_name=data['first_name'],
                last_name=data['last_name'],
                role=data['role'],
                phone=data.get('phone', ''),
                department=data.get('department', '')
            )
            
            return Response({
                'message': 'User registered successfully',
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'name': f"{user.first_name} {user.last_name}",
                    'role': user.role
                }
            }, status=status.HTTP_201_CREATED)
            
        except IntegrityError as e:
            return Response(
                {'error': 'Database error occurred'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
class PasswordResetView(APIView):
    """
    Handle password reset requests
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            try:
                user = User.objects.get(email=email)
                # Send password reset email (implementation depends on your email service)
                # This is a placeholder for actual email sending logic
                return Response(
                    {'message': 'Password reset link sent to email'},
                    status=status.HTTP_200_OK
                )
            except User.DoesNotExist:
                return Response(
                    {'error': 'User with this email does not exist'},
                    status=status.HTTP_404_NOT_FOUND
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class PasswordChangeView(APIView):
    """
    Handle password changes for authenticated users
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        old_password = request.data.get('old_password')
        new_password = request.data.get('new_password')
        
        if not check_password(old_password, request.user.password):
            return Response(
                {'error': 'Current password is incorrect'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        request.user.set_password(new_password)
        request.user.save()
        
        return Response(
            {'message': 'Password updated successfully'},
            status=status.HTTP_200_OK
        )
        
class RefreshTokenView(APIView):
    """
    Refresh JWT token
    """
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            token = RefreshToken(refresh_token)
            new_access = str(token.access_token)
            
            return Response({
                'access': new_access
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Token refresh error: {str(e)}")
            return Response(
                {'error': 'Invalid or expired refresh token'},
                status=status.HTTP_401_UNAUTHORIZED
            )

class UserListView(ListAPIView):
    """
    Returns a list of all registered users
    """
    queryset = User.objects.all()
    serializer_class = UserListSerializer
    permission_classes = [AllowAny]  

class UserProfileView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            profile_data = {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'is_active': user.is_active,
                'date_joined': user.date_joined,
                'last_login': user.last_login,
                # Add any additional profile fields
            }
            return Response(profile_data)
        except Exception as e:
            print(f"Error in profile view: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class UserProfileUpdateView(UpdateAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user