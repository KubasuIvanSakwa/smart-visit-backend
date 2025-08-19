from django.urls import path
from .views import (
    CustomTokenObtainPairView,
    VerifyTokenView,
    LogoutView,
    RegisterView,
    PasswordResetView,
    PasswordChangeView,
    UserListView,
    UserProfileView,
    UserProfileUpdateView
)

urlpatterns = [
    path('login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('verify/', VerifyTokenView.as_view(), name='token_verify'),
    path('logout/', LogoutView.as_view(), name='token_logout'),
    path('register/', RegisterView.as_view(), name='register'),
    path('password/reset/', PasswordResetView.as_view(), name='password_reset'),
    path('password/change/', PasswordChangeView.as_view(), name='password_change'),
    path('users/', UserListView.as_view(), name='user_list'),
    path('user/profile/', UserProfileView.as_view(), name='user-profile'),
    path('profile/update/', UserProfileUpdateView.as_view(), name='profile-update'),
]