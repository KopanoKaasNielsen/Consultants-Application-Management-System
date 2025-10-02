"""Shared Django settings for the backend project."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Sequence

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


def _append_unique(items: list[str], value: str) -> None:
    """Append a value to a list only if it does not already exist."""

    if value and value not in items:
        items.append(value)


def _clean_hostname(hostname: str) -> str:
    """Normalise hostnames by removing protocols and trailing slashes."""

    cleaned = hostname.strip().removeprefix("https://").removeprefix("http://")
    return cleaned.rstrip("/")


def _get_render_hosts() -> list[str]:
    """Collect Render deployment hostnames when available."""

    render_host = os.getenv("RENDER_EXTERNAL_HOSTNAME")
    if not render_host:
        return []

    cleaned_host = _clean_hostname(render_host)
    if not cleaned_host:
        return []

    hosts = [cleaned_host]

    bare_host = cleaned_host.split(":", maxsplit=1)[0]
    if bare_host and bare_host != cleaned_host:
        hosts.append(bare_host)

    return hosts


def build_allowed_hosts(default_hosts: Sequence[str] | None = None) -> list[str]:
    """Build the ALLOWED_HOSTS list from the environment."""

    hosts_env = os.getenv("DJANGO_ALLOWED_HOSTS")
    if hosts_env:
        hosts = [host.strip() for host in hosts_env.split(",") if host.strip()]
    else:
        hosts = list(default_hosts or [])

    for render_host in _get_render_hosts():
        _append_unique(hosts, render_host)

    return hosts


def build_csrf_trusted_origins(allowed_hosts: Iterable[str]) -> list[str]:
    """Return CSRF trusted origins matching allowed hosts where possible."""

    origins_env = os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS")
    if origins_env:
        origins = [origin.strip() for origin in origins_env.split(",") if origin.strip()]
    else:
        origins = []

    if not origins_env:
        for host in allowed_hosts:
            if host in {"localhost", "127.0.0.1"}:
                continue
            scheme = "https" if not host.startswith("http") else ""
            origins.append(f"{scheme}://{host}" if scheme else host)

    for render_host in _get_render_hosts():
        scheme = "https" if not render_host.startswith("http") else ""
        origin = f"{scheme}://{render_host}" if scheme else render_host
        _append_unique(origins, origin)

    return origins


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
