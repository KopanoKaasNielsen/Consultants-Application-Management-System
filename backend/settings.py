"""Base Django settings for the backend project."""

from __future__ import annotations

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

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


def get_allowed_hosts() -> list[str]:
    """Build the ALLOWED_HOSTS list from the environment."""

    hosts = os.getenv("DJANGO_ALLOWED_HOSTS")
    if not hosts:
        return ["localhost", "127.0.0.1"]
    return [host.strip() for host in hosts.split(",") if host.strip()]


ALLOWED_HOSTS = get_allowed_hosts()


def get_csrf_trusted_origins() -> list[str]:
    """Return CSRF trusted origins matching allowed hosts where possible."""

    origins_env = os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS")
    if origins_env:
        return [origin.strip() for origin in origins_env.split(",") if origin.strip()]

    origins: list[str] = []
    for host in ALLOWED_HOSTS:
        if host in {"localhost", "127.0.0.1"}:
            continue
        scheme = "https" if not host.startswith("http") else ""
        origins.append(f"{scheme}://{host}" if scheme else host)
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
LOGOUT_REDIRECT_URL = '/accounts/login/'
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

