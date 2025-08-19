from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve
from django.http import JsonResponse
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

def debug_urls(request):
    from django.urls import get_resolver
    urls = []
    for url_pattern in get_resolver().url_patterns:
        urls.append(str(url_pattern.pattern))
    return JsonResponse({'available_urls': urls})

def root_view(request):
    return JsonResponse({"message": "Welcome to KREP SmartVisit API!"})

# 👇 Add this debug view at the root level
def debug_test(request):
    return JsonResponse({"status": "success", "message": "Debug test working!"})

urlpatterns = [
    path('', root_view),
    path('admin/', admin.site.urls),
    path('', include('authentication.urls')),
    
    # API routes
    path('api/', include([
        path('', include('visitors.urls')),  # Now properly nested
        path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
        path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
        path('auth/', include('authentication.urls')),
        path('debug-test/', debug_test), 
    ])),
    
    path('debug-urls/', debug_urls),
    
    # Static media files
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)