"""Base Django settings for the backend project."""

from __future__ import annotations

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from django.urls import reverse_lazy

import dj_database_url


def get_env_bool(name: str, default: bool = False) -> bool:
    """Return a boolean for an environment variable.

    Accepts common truthy values ("true", "1", "yes").
    """

    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"true", "1", "yes"}


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


DEBUG = get_env_bool("DJANGO_DEBUG", default=True)


def get_secret_key() -> str:
    """Fetch the Django secret key from the environment."""

    secret_key = os.getenv("DJANGO_SECRET_KEY") or os.getenv("SECRET_KEY")
    if secret_key:
        return secret_key
    if DEBUG:
        # Provide a predictable key only for local development to avoid crashes
        return "django-insecure-development-key"
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set in production environments.")


# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = get_secret_key()


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


def get_allowed_hosts() -> list[str]:
    """Build the ALLOWED_HOSTS list from the environment."""

    hosts_env = os.getenv("DJANGO_ALLOWED_HOSTS")
    if hosts_env:
        hosts = [host.strip() for host in hosts_env.split(",") if host.strip()]
    else:
        # Include common loopback addresses plus 0.0.0.0 so that platform
        # health checks using that host header don't trigger a 400 response.
        hosts = ["localhost", "127.0.0.1", "0.0.0.0"]

    for render_host in _get_render_hosts():
        _append_unique(hosts, render_host)

    return hosts


ALLOWED_HOSTS = get_allowed_hosts()


def get_csrf_trusted_origins() -> list[str]:
    """Return CSRF trusted origins matching allowed hosts where possible."""

    origins_env = os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS")
    if origins_env:
        origins = [origin.strip() for origin in origins_env.split(",") if origin.strip()]
    else:
        origins = []

    if not origins_env:
        for host in ALLOWED_HOSTS:
            if host in {"localhost", "127.0.0.1"}:
                continue
            scheme = "https" if not host.startswith("http") else ""
            origins.append(f"{scheme}://{host}" if scheme else host)

    for render_host in _get_render_hosts():
        scheme = "https" if not render_host.startswith("http") else ""
        origin = f"{scheme}://{render_host}" if scheme else render_host
        _append_unique(origins, origin)

    return origins


CSRF_TRUSTED_ORIGINS = get_csrf_trusted_origins()



# Application definition

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


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DATABASES = {
    'default': dj_database_url.config(default='sqlite:///db.sqlite3', conn_max_age=600)
}



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



# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Static & Media Configuration
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static'] if DEBUG else []

if os.getenv('DJANGO_ENV') == 'production':
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

STATIC_ROOT = BASE_DIR / 'staticfiles'
# Simplified static file serving.
# https://warehouse.python.org/project/whitenoise/

