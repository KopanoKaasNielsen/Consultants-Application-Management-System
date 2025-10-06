"""Shared Django settings for the backend project."""

from __future__ import annotations

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from django.urls import reverse_lazy

import dj_database_url
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration


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
    'apps.consultants',
    'apps.vetting',
    'apps.decisions',
    'apps.certificates',
    'apps.users',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
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
            ],
        },
    },
]

WSGI_APPLICATION = 'backend.wsgi.application'

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

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# Configure monitoring once settings are imported.
init_sentry()
