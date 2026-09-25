"""
Django settings for config project.

"""

import os
from pathlib import Path

import dj_database_url
from decouple import config
from django.core.exceptions import ImproperlyConfigured

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
DEVELOPMENT_SECRET_KEY = 'django-insecure-development-only-change-me'
SECRET_KEY = config(
    'SECRET_KEY',
    default=DEVELOPMENT_SECRET_KEY,
)

def env_list(name, default=''):
    """Read a comma-separated environment variable as a clean list."""
    return [item.strip() for item in config(name, default=default).split(',') if item.strip()]


def env_bool(name, default=False):
    """Treat only explicit truthy values as true; unknown values stay safe."""
    value = config(name, default=str(default))
    return str(value).strip().lower() in {'1', 'true', 'yes', 'on'}


# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env_bool('DEBUG', default=True)

if not DEBUG and SECRET_KEY == DEVELOPMENT_SECRET_KEY:
    raise ImproperlyConfigured('SECRET_KEY must be set when DEBUG is false.')


ALLOWED_HOSTS = env_list(
    'ALLOWED_HOSTS',
    'localhost,127.0.0.1,testserver,.onrender.com',
)
render_hostname = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if render_hostname and render_hostname not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(render_hostname)

CSRF_TRUSTED_ORIGINS = env_list('CSRF_TRUSTED_ORIGINS')
if render_hostname:
    render_origin = f'https://{render_hostname}'
    if render_origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(render_origin)


# Application definition

INSTALLED_APPS = [
    'daphne',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'channels',
    'storages',
    # 'drf_yasg',  # Disabled - Python 3.13 compatibility issue
    'courses',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'courses.context_processors.notification_count',  
                'courses.context_processors.deployment_capabilities',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DATABASE_URL = config('DATABASE_URL', default='')
if not DEBUG and not DATABASE_URL:
    raise ImproperlyConfigured('DATABASE_URL must be set when DEBUG is false.')

DATABASES = {
    'default': dj_database_url.parse(
        DATABASE_URL or f'sqlite:///{BASE_DIR / "db.sqlite3"}',
        conn_max_age=config('DB_CONN_MAX_AGE', default=60, cast=int),
        conn_health_checks=True,
    )
}
if DATABASES['default']['ENGINE'] == 'django.db.backends.postgresql':
    pooled_host = '-pooler.' in DATABASES['default'].get('HOST', '')
    DATABASES['default']['DISABLE_SERVER_SIDE_CURSORS'] = env_bool(
        'DB_DISABLE_SERVER_SIDE_CURSORS', default=pooled_host
    )


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

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


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Static assets are built into the deployment image. User uploads use an
# S3-compatible object store when configured and never need Render's filesystem.
AWS_STORAGE_BUCKET_NAME = config('AWS_STORAGE_BUCKET_NAME', default='')
MEDIA_UPLOADS_ENABLED = config(
    'MEDIA_UPLOADS_ENABLED', default='',
)
MEDIA_UPLOADS_ENABLED = (
    env_bool('MEDIA_UPLOADS_ENABLED')
    if MEDIA_UPLOADS_ENABLED != ''
    else bool(DEBUG or AWS_STORAGE_BUCKET_NAME)
)
if not DEBUG and MEDIA_UPLOADS_ENABLED and not AWS_STORAGE_BUCKET_NAME:
    raise ImproperlyConfigured(
        'Persistent object storage is required for production media uploads.'
    )

STORAGES = {
    'staticfiles': {
        'BACKEND': (
            'django.contrib.staticfiles.storage.StaticFilesStorage'
            if DEBUG
            else 'whitenoise.storage.CompressedManifestStaticFilesStorage'
        ),
    },
}

if AWS_STORAGE_BUCKET_NAME:
    STORAGES['default'] = {'BACKEND': 'storages.backends.s3.S3Storage'}
    AWS_ACCESS_KEY_ID = config('AWS_ACCESS_KEY_ID', default='')
    AWS_SECRET_ACCESS_KEY = config('AWS_SECRET_ACCESS_KEY', default='')
    AWS_S3_REGION_NAME = config('AWS_S3_REGION_NAME', default='') or None
    AWS_S3_ENDPOINT_URL = config('AWS_S3_ENDPOINT_URL', default='') or None
    AWS_S3_CUSTOM_DOMAIN = config('AWS_S3_CUSTOM_DOMAIN', default='') or None
    AWS_DEFAULT_ACL = None
    AWS_QUERYSTRING_AUTH = env_bool('AWS_QUERYSTRING_AUTH', default=True)
    AWS_S3_FILE_OVERWRITE = False
else:
    STORAGES['default'] = {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    }

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ============================================
# REST FRAMEWORK CONFIGURATION
# Enables both JSON API and browsable HTML interface
# ============================================
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.BasicAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',           # JSON responses
        'rest_framework.renderers.BrowsableAPIRenderer',   # Interactive HTML docs
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

# Application caching is optional. The complete stack uses a dedicated Redis
# database; lightweight development and the public demo use process-local cache.
CACHE_URL = config('CACHE_URL', default='')
if CACHE_URL:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': CACHE_URL,
            'KEY_PREFIX': 'elearning',
            'TIMEOUT': 300,
        }
    }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'elearning-local-cache',
        }
    }

# ============================================
# CELERY CONFIGURATION
# Background task processing for async emails
# ============================================ 
REDIS_URL = config('REDIS_URL', default='')
CELERY_ENABLED = (
    env_bool('CELERY_ENABLED')
    if config('CELERY_ENABLED', default='') != ''
    else bool(REDIS_URL)
)
CELERY_BROKER_URL = config(
    'CELERY_BROKER_URL',
    default=REDIS_URL or 'redis://localhost:6379/0',
)
CELERY_RESULT_BACKEND = config(
    'CELERY_RESULT_BACKEND',
    default=REDIS_URL or 'redis://localhost:6379/0',
)
CELERY_TASK_PUBLISH_RETRY = False
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

# Serialization format for task messages
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'

# ============================================
# EMAIL CONFIGURATION
# Console backend for development (prints to terminal)
# ============================================
EMAIL_BACKEND = config(
    'EMAIL_BACKEND',
    default='django.core.mail.backends.console.EmailBackend',
)
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@elearning.com')
EMAIL_HOST = config('EMAIL_HOST', default='')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = env_bool('EMAIL_USE_TLS', default=True)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')

# ============================================
# DJANGO CHANNELS CONFIGURATION
# WebSocket support for real-time chat
# ============================================ 
ASGI_APPLICATION = 'config.asgi.application'

if REDIS_URL:
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels_redis.core.RedisChannelLayer',
            'CONFIG': {'hosts': [REDIS_URL]},
        },
    }
else:
    # One-process fallback for the public demo. Redis remains the full-stack
    # implementation used by Docker Compose and horizontally scaled deployments.
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels.layers.InMemoryChannelLayer',
        },
    }

# ============================================
# EXTERNAL API KEYS
# ============================================
# TextRazor API for AI course difficulty analysis
# Falls back to keyword analysis if not provided
TEXTRAZOR_API_KEY = config('TEXTRAZOR_API_KEY', default='')
EXTERNAL_API_TIMEOUT = config('EXTERNAL_API_TIMEOUT', default=5, cast=int)
TEXTRAZOR_TIMEOUT = config('TEXTRAZOR_TIMEOUT', default=15, cast=int)
ALLOW_INSTRUCTOR_REGISTRATION = env_bool(
    'ALLOW_INSTRUCTOR_REGISTRATION', default=DEBUG
)

# ============================================
# AUTHENTICATION SETTINGS
# ============================================ 
LOGIN_URL = 'courses:login'              # Redirect here when login required
LOGIN_REDIRECT_URL = 'courses:home'      # Redirect after successful login
LOGOUT_REDIRECT_URL = 'courses:home'     # Redirect after logout

AUTHENTICATION_BACKENDS = [
    'courses.backends.EmailBackend',
    'django.contrib.auth.backends.ModelBackend',
]

# Session configuration
SESSION_COOKIE_AGE = 1209600             # Session expires after 14 days of inactivity
SESSION_EXPIRE_AT_BROWSER_CLOSE = False  # Keep session when browser closes
SESSION_COOKIE_HTTPONLY = True           # Prevent JavaScript access (security)
SESSION_COOKIE_NAME = 'sessionid'        # Cookie name

# ============================================
# DJANGO MESSAGES FRAMEWORK
# ============================================

from django.contrib.messages import constants as messages

MESSAGE_TAGS = {
    messages.DEBUG: 'debug',      # Gray (rarely used)
    messages.INFO: 'info',        # Blue
    messages.SUCCESS: 'success',  # Green
    messages.WARNING: 'warning',  # Yellow
    messages.ERROR: 'danger',     # Red 
}

# ============================================
# MEDIA FILES CONFIGURATION
# ============================================

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
FILE_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10MB

# Production security defaults. Proxy SSL headers are required because Render
# terminates TLS before forwarding requests to Django.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = env_bool('SECURE_SSL_REDIRECT', default=not DEBUG)
SECURE_HSTS_SECONDS = config('SECURE_HSTS_SECONDS', default=0, cast=int)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool(
    'SECURE_HSTS_INCLUDE_SUBDOMAINS', default=bool(SECURE_HSTS_SECONDS)
)
SECURE_HSTS_PRELOAD = env_bool(
    'SECURE_HSTS_PRELOAD', default=bool(SECURE_HSTS_SECONDS)
)

LOG_LEVEL = config('LOG_LEVEL', default='INFO').upper()
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '{levelname} {asctime} {name} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'standard',
        },
    },
    'root': {'handlers': ['console'], 'level': LOG_LEVEL},
}
