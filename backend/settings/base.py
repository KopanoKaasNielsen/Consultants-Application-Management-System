"""Shared Django settings for the backend project."""

from __future__ import annotations

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from django.urls import reverse_lazy

import dj_database_url
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

from consultant_app import settings as consultant_celery_settings


BASE_DIR = Path(__file__).resolve().parent.parent.parent


def get_env_bool(name: str, default: bool = False) -> bool:
    """Return a boolean for an environment variable."""

    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"true", "1", "yes"}


def get_secret_key(debug: bool) -> str:
    """Fetch the Django secret key from the environment."""

    secret_key = os.getenv("DJANGO_SECRET_KEY") or os.getenv("SECRET_KEY")
    if secret_key:
        return secret_key
    if debug:
        # Provide a predictable key only for local development to avoid crashes
        return "django-insecure-development-key"
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY must be set in production environments."
    )

ALLOWED_HOSTS = os.getenv(
    "ALLOWED_HOSTS",
    "localhost,127.0.0.1,consultant-app-156x.onrender.com,.onrender.com",
).split(",")
CSRF_TRUSTED_ORIGINS = os.getenv(
    "CSRF_TRUSTED_ORIGINS",
    "https://consultant-app-156x.onrender.com,https://*.onrender.com",
).split(",")
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")


def _get_sample_rate(name: str, default: float) -> float:
    """Fetch a float configuration value from the environment."""

    value = os.getenv(name)
    if value is None:
        return default

    try:
        return float(value)
    except ValueError:
        return default


def init_sentry() -> None:
    """Configure Sentry monitoring when a DSN is available."""

    dsn = os.getenv("SENTRY_DSN")
    if not dsn:
        return None

    sentry_sdk.init(
        dsn=dsn,
        integrations=[DjangoIntegration()],
        send_default_pii=False,
        traces_sample_rate=_get_sample_rate("SENTRY_TRACES_SAMPLE_RATE", 0.2),
        profiles_sample_rate=_get_sample_rate("SENTRY_PROFILES_SAMPLE_RATE", 0.0),
    )
    return None


INSTALLED_APPS = [
    'channels',
    'consultant_app.apps.ConsultantAppConfig',
    'apps.api',
    'apps.consultants',
    'apps.vetting',
    'apps.decisions',
    'apps.certificates',
    'apps.security',
    'apps.users',
    'django_crontab',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

# Ensure Django REST framework is always available for tests and runtime features
REST_FRAMEWORK_APP = 'rest_framework'
if REST_FRAMEWORK_APP not in INSTALLED_APPS:
    INSTALLED_APPS.insert(1, REST_FRAMEWORK_APP)

REST_FRAMEWORK = {
    'DEFAULT_THROTTLE_CLASSES': [
        'apps.api.throttling.RoleBasedRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'role': '60/min',
    },
    'ROLE_BASED_THROTTLE_RATES': {
        'consultant': '60/min',
        'staff': '30/min',
        'board': '15/min',
    },
}

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'apps.users.middleware.JWTAuthenticationMiddleware',
    'middleware.role_access.RoleAccessMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
]

ROOT_URLCONF = 'backend.urls'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = reverse_lazy('login')
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
                'apps.users.context_processors.role_flags',
                'apps.consultants.context_processors.consultant_notifications',
            ],
        },
    },
]

ASGI_APPLICATION = 'backend.asgi.application'
WSGI_APPLICATION = 'backend.wsgi.application'


def _build_channel_layers() -> dict[str, dict[str, object]]:
    """Return the configured channel layers with a graceful fallback."""

    redis_url = os.getenv("CHANNEL_REDIS_URL") or os.getenv("REDIS_URL")
    if redis_url:
        return {
            'default': {
                'BACKEND': 'channels_redis.core.RedisChannelLayer',
                'CONFIG': {
                    'hosts': [redis_url],
                },
            }
        }

    return {
        'default': {
            'BACKEND': 'channels.layers.InMemoryChannelLayer',
        }
    }


CHANNEL_LAYERS = _build_channel_layers()

DATABASES = {
    'default': dj_database_url.config(default='sqlite:///db.sqlite3', conn_max_age=600)
}

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

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS: list[str] = []
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

CERTIFICATE_VERIFY_BASE_URL = os.getenv("CERTIFICATE_VERIFY_BASE_URL", "")

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# Structured logging configuration persisting key workflow actions.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {
            'format': '%(levelname)s %(name)s %(message)s',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'database': {
            'level': 'INFO',
            'class': 'apps.consultants.logging.DatabaseLogHandler',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
        },
        'apps.consultants': {
            'handlers': ['console', 'database'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps.users': {
            'handlers': ['console', 'database'],
            'level': 'INFO',
            'propagate': False,
        },
        'consultant_app': {
            'handlers': ['console', 'database'],
            'level': 'INFO',
            'propagate': False,
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    },
}


# Email configuration sourced from environment variables for secure delivery.
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend"
)
EMAIL_HOST = os.getenv("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = get_env_bool("EMAIL_USE_TLS", True)
EMAIL_USE_SSL = get_env_bool("EMAIL_USE_SSL", False)
DEFAULT_FROM_EMAIL = os.getenv(
    "DEFAULT_FROM_EMAIL", "no-reply@consultant-management.local"
)


# Celery configuration shared with the worker process.
CELERY_BROKER_URL = consultant_celery_settings.CELERY_BROKER_URL
CELERY_RESULT_BACKEND = consultant_celery_settings.CELERY_RESULT_BACKEND
CELERY_TASK_DEFAULT_QUEUE = consultant_celery_settings.CELERY_TASK_DEFAULT_QUEUE
CELERY_TASK_DEFAULT_EXCHANGE = consultant_celery_settings.CELERY_TASK_DEFAULT_EXCHANGE
CELERY_TASK_DEFAULT_ROUTING_KEY = (
    consultant_celery_settings.CELERY_TASK_DEFAULT_ROUTING_KEY
)
CELERY_TASK_ALWAYS_EAGER = consultant_celery_settings.CELERY_TASK_ALWAYS_EAGER
CELERY_TASK_EAGER_PROPAGATES = (
    consultant_celery_settings.CELERY_TASK_EAGER_PROPAGATES
)
CELERY_TASK_ACKS_LATE = consultant_celery_settings.CELERY_TASK_ACKS_LATE
CELERY_TASK_SOFT_TIME_LIMIT = (
    consultant_celery_settings.CELERY_TASK_SOFT_TIME_LIMIT
)
CELERY_TASK_TIME_LIMIT = consultant_celery_settings.CELERY_TASK_TIME_LIMIT
CELERY_BEAT_SCHEDULE = consultant_celery_settings.CELERY_BEAT_SCHEDULE

ADMIN_REPORT_RECIPIENTS = consultant_celery_settings.ADMIN_REPORT_RECIPIENTS
ADMIN_REPORT_FROM_EMAIL = consultant_celery_settings.ADMIN_REPORT_FROM_EMAIL
ADMIN_REPORT_BASE_URL = consultant_celery_settings.ADMIN_REPORT_BASE_URL
ADMIN_REPORT_ATTACHMENT_PREFIX = (
    consultant_celery_settings.ADMIN_REPORT_ATTACHMENT_PREFIX
)
ADMIN_REPORT_SUBJECTS = consultant_celery_settings.ADMIN_REPORT_SUBJECTS


# Weekly analytics email scheduling (every Monday at 08:00 UTC).
CRONJOBS = [
    (
        '0 8 * * 1',
        'django.core.management.call_command',
        ['send_weekly_analytics_report'],
    )
]


# Configure monitoring once settings are imported.
init_sentry()


# JWT authentication configuration
JWT_AUTH_SECRET = os.getenv("JWT_AUTH_SECRET")
JWT_AUTH_ALGORITHM = os.getenv("JWT_AUTH_ALGORITHM", "HS256")
_jwt_algorithms_env = os.getenv("JWT_AUTH_ALGORITHMS")
JWT_AUTH_ALGORITHMS = (
    tuple(algo.strip() for algo in _jwt_algorithms_env.split(",") if algo.strip())
    if _jwt_algorithms_env
    else None
)
