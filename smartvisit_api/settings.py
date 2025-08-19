from pathlib import Path
import os
from datetime import timedelta
from typing import List

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-#pqr&16mjrz8!8l$f#fbf*2fgnvzaxzg+*li@f%2=u4+ohqti%'

DEBUG = True

ALLOWED_HOSTS: List[str] = ["*"]

# Custom user model
AUTH_USER_MODEL = 'visitors.CustomUser'

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # 3rd party
    'rest_framework',
    'rest_framework_simplejwt',
    'django_filters',
    'corsheaders',
    
    # Your apps
    'visitors',
    'notifications',
    'channels',
    'authentication.apps.AuthenticationConfig',
    'django_extensions',
]

LOCALE_PATHS = [
    os.path.join(BASE_DIR, 'locale'),  # Adjust the path as necessary
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',   
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'smartvisit_api.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, "frontend_dist")],  # ✅ React build folder
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'smartvisit_api.wsgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

ASGI_APPLICATION = 'krep_smartvisit.asgi.application' 

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Nairobi'
USE_I18N = True
USE_TZ = True

# Static & Media files
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, "frontend_dist/assets"), 
]
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# CORS
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
CORS_ALLOW_ALL_ORIGINS = True

# REST Framework & Filters
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_FILTER_BACKENDS': ['django_filters.rest_framework.DjangoFilterBackend'],
}

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",  # 👈 Dev only (no Redis required)
    },
}

# JWT Configuration
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'AUTH_HEADER_TYPES': ('Bearer',),
}

AUTHENTICATION_BACKENDS = [
    'visitors.backends.EmailBackend',             
    "django.contrib.auth.backends.ModelBackend",   
]

# Pusher Configuration
PUSHER_APP_ID = "2022219"
PUSHER_KEY = "6fdb9e38bb8d77e577c3"
PUSHER_SECRET = "4f32f1729df7270251a8"
PUSHER_CLUSTER = "mt1"
PUSHER_SSL = True

# WhatsApp Business API Config
WHATSAPP_PHONE_ID = 'your_whatsapp_phone_id'
WHATSAPP_ACCESS_TOKEN = 'your_whatsapp_access_token'

# Email Notifications
DEFAULT_FROM_EMAIL = 'elvis@krepsoftware.co.ke'
