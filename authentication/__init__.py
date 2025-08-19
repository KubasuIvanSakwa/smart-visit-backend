# authentication/__init__.py

# Option 1: Minimal version (recommended)
default_app_config = 'authentication.apps.AuthenticationConfig'

# Option 2: If you need to expose views at package level (alternative)
# def __getattr__(name):
#     if name in [
#         'CustomTokenObtainPairView',
#         'VerifyTokenView',
#         'LogoutView',
#         'RegisterView',
#         'RefreshTokenView',
#         'PasswordResetView',
#         'PasswordChangeView'
#     ]:
#         from .views import name
#         return name
#     raise AttributeError(f"module 'authentication' has no attribute '{name}'")