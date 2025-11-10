"""Shared Django settings for the backend project."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable, Sequence
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured
from django.urls import reverse_lazy

import dj_database_url
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

from consultant_app import settings as consultant_celery_settings


BASE_DIR = Path(__file__).resolve().parent.parent.parent


def _get_env(name: str) -> str | None:
    """Return the raw value for ``name`` if it exists."""

    return os.getenv(name)


def get_env_bool(name: str, default: bool = False) -> bool:
    """Return a boolean for an environment variable."""

    value = _get_env(name)
    if value is None:
        return default
    return value.lower() in {"true", "1", "yes"}


def get_env_int(name: str, default: int) -> int:
    """Return an integer for ``name`` or ``default`` if unset."""

    value = _get_env(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as exc:  # pragma: no cover - defensive path
        raise ImproperlyConfigured(
            f"Environment variable {name} must be an integer."
        ) from exc


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

DEFAULT_ALLOWED_HOSTS = (
    "localhost",
    "127.0.0.1",
)


_SETTINGS_MODULE = os.getenv("DJANGO_SETTINGS_MODULE", "")
_IS_LOCAL_SETTINGS = _SETTINGS_MODULE.endswith(".dev")
_DEFAULT_DEBUG_STATE = get_env_bool(
    "DJANGO_DEBUG", default=_IS_LOCAL_SETTINGS
)


def _normalise_list(values: Iterable[str]) -> list[str]:
    """Return a list of unique, stripped values preserving order."""

    normalised: list[str] = []
    for value in values:
        candidate = value.strip()
        if not candidate or candidate in normalised:
            continue
        normalised.append(candidate)
    return normalised


def _read_hosts_from_env(env_var: str) -> list[str]:
    """Return a list of hosts defined in ``env_var``."""

    raw_value = os.getenv(env_var)
    if not raw_value:
        return []
    return _normalise_list(raw_value.split(","))


def get_allowed_hosts(env_var: str, default: Iterable[str] | None = None) -> list[str]:
    """Read a comma-separated list of hosts from an environment variable."""

    hosts = _read_hosts_from_env(env_var)
    if hosts:
        return hosts
    if default is None:
        default = DEFAULT_ALLOWED_HOSTS
    return list(default)


def _get_render_allowed_hosts() -> list[str]:
    """Return hostnames automatically exposed by Render deployments."""

    hosts: list[str] = []
    render_hostname = os.getenv("RENDER_EXTERNAL_HOSTNAME")
    if render_hostname:
        hosts.append(render_hostname)

    render_external_url = os.getenv("RENDER_EXTERNAL_URL")
    if render_external_url:
        parsed = urlsplit(render_external_url)
        if parsed.hostname:
            hosts.append(parsed.hostname)

    hosts.append(".onrender.com")

    return _normalise_list(hosts)


def build_allowed_hosts(
    *env_vars: str,
    default: Iterable[str] | None = None,
    include_render_hosts: bool = True,
) -> list[str]:
    """Aggregate allowed hosts from configuration and Render defaults."""

    hosts: list[str] = []
    for env_var in env_vars:
        hosts.extend(_read_hosts_from_env(env_var))

    if not hosts:
        if default is None:
            default = DEFAULT_ALLOWED_HOSTS
        hosts.extend(default)

    if include_render_hosts:
        hosts.extend(_get_render_allowed_hosts())

    return _normalise_list(hosts)


def get_csrf_trusted_origins(
    env_var: str,
    default: Iterable[str] | None = None,
) -> list[str]:
    """Fetch trusted origins allowing override per environment."""

    raw_value = os.getenv(env_var)
    if raw_value:
        return _normalise_list(raw_value.split(","))
    if default is None:
        return []
    return list(default)


ALLOWED_HOSTS = build_allowed_hosts("ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = get_csrf_trusted_origins(
    "CSRF_TRUSTED_ORIGINS",
    default=("https://localhost", "https://127.0.0.1"),
)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SECURE_SSL_REDIRECT = get_env_bool(
    "DJANGO_SECURE_SSL_REDIRECT", default=not _DEFAULT_DEBUG_STATE
)
SESSION_COOKIE_SECURE = get_env_bool(
    "DJANGO_SESSION_COOKIE_SECURE", default=not _DEFAULT_DEBUG_STATE
)
SESSION_COOKIE_HTTPONLY = get_env_bool(
    "DJANGO_SESSION_COOKIE_HTTPONLY", default=True
)
SESSION_COOKIE_SAMESITE = os.getenv("DJANGO_SESSION_COOKIE_SAMESITE", "Lax")
CSRF_COOKIE_SECURE = get_env_bool(
    "DJANGO_CSRF_COOKIE_SECURE", default=not _DEFAULT_DEBUG_STATE
)
CSRF_COOKIE_HTTPONLY = get_env_bool(
    "DJANGO_CSRF_COOKIE_HTTPONLY", default=False
)
CSRF_COOKIE_SAMESITE = os.getenv("DJANGO_CSRF_COOKIE_SAMESITE", "Lax")
SECURE_CONTENT_TYPE_NOSNIFF = get_env_bool(
    "DJANGO_SECURE_CONTENT_TYPE_NOSNIFF", default=True
)
SECURE_REFERRER_POLICY = os.getenv("DJANGO_SECURE_REFERRER_POLICY", "same-origin")

_default_hsts_seconds = 0
SECURE_HSTS_SECONDS = get_env_int(
    "DJANGO_SECURE_HSTS_SECONDS", default=_default_hsts_seconds
)
SECURE_HSTS_INCLUDE_SUBDOMAINS = get_env_bool(
    "DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS",
    default=SECURE_HSTS_SECONDS > 0,
)
SECURE_HSTS_PRELOAD = get_env_bool(
    "DJANGO_SECURE_HSTS_PRELOAD", default=False
)
X_FRAME_OPTIONS = os.getenv("DJANGO_X_FRAME_OPTIONS", "DENY")


def _get_sample_rate(name: str, default: float) -> float:
    """Fetch a float configuration value from the environment."""

    value = os.getenv(name)
    if value is None:
        return default

    try:
        return float(value)
    except ValueError:
        return default


def _split_env_set(name: str) -> set[str]:
    """Return a set of comma separated values for an environment variable."""

    raw_value = os.getenv(name, "")
    return {item.strip() for item in raw_value.split(",") if item.strip()}


def init_sentry() -> None:
    """Configure Sentry monitoring when a DSN is available."""

    dsn = os.getenv("SENTRY_DSN")
    if not dsn:
        return None

    environment = (
        os.getenv("SENTRY_ENVIRONMENT")
        or os.getenv("DJANGO_ENV")
        or os.getenv("ENVIRONMENT")
        or ("development" if get_env_bool("DJANGO_DEBUG", True) else "production")
    )

    sentry_sdk.init(
        dsn=dsn,
        integrations=[DjangoIntegration()],
        environment=environment,
        send_default_pii=False,
        traces_sample_rate=_get_sample_rate("SENTRY_TRACES_SAMPLE_RATE", 0.2),
        profiles_sample_rate=_get_sample_rate("SENTRY_PROFILES_SAMPLE_RATE", 0.0),
    )
    sentry_sdk.set_tag("environment", environment)
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

def _build_test_settings(parsed: dict[str, str]) -> dict[str, str]:
    """Translate a parsed database URL into a Django TEST settings block."""

    keys = ("NAME", "USER", "PASSWORD", "HOST", "PORT", "ENGINE", "OPTIONS")
    return {key: parsed[key] for key in keys if key in parsed}


def _first_env_value(names: Sequence[str]) -> str | None:
    """Return the first populated environment variable from ``names``."""

    for name in names:
        if not name:
            continue
        value = os.getenv(name)
        if value:
            return value
    return None


def _apply_host_suffix(config: dict[str, object], host_suffix: str) -> None:
    """Append ``host_suffix`` to any host fields missing a domain segment."""

    host = config.get("HOST")
    if isinstance(host, str) and host and "." not in host:
        if not host.endswith(host_suffix):
            config["HOST"] = f"{host}{host_suffix}"

    test_settings = config.get("TEST")
    if isinstance(test_settings, dict):
        _apply_host_suffix(test_settings, host_suffix)


def _component_prefix_from_env_var(env_var: str) -> str:
    """Return the base prefix used for discrete database env vars."""

    if env_var.endswith("_URL"):
        return env_var[: -len("_URL")]
    return env_var


def _load_options_from_env(env_var: str) -> dict[str, object] | None:
    """Parse JSON database OPTIONS from ``env_var`` if present."""

    raw_value = os.getenv(env_var)
    if not raw_value:
        return None
    try:
        loaded = json.loads(raw_value)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive path
        raise ImproperlyConfigured(
            f"Environment variable {env_var} must contain valid JSON."
        ) from exc
    if not isinstance(loaded, dict):
        raise ImproperlyConfigured(
            f"Environment variable {env_var} must decode to a JSON object."
        )
    return loaded


def _normalise_engine_name(value: str | None) -> str | None:
    """Normalise shorthand engine identifiers to Django backend paths."""

    if not value:
        return None
    candidate = value.strip()
    if not candidate:
        return None
    lowered = candidate.lower()
    if lowered in {"postgres", "postgresql", "psql"}:
        return "django.db.backends.postgresql"
    if lowered in {
        "postgresql_psycopg2",
        "django.db.backends.postgresql_psycopg2",
    }:
        return "django.db.backends.postgresql"
    return candidate


def _build_component_config(prefix: str, *, conn_max_age: int) -> dict[str, object] | None:
    """Construct a database config from discrete environment variables."""

    prefix = prefix.rstrip("_")
    keys = ("NAME", "USER", "PASSWORD", "HOST", "PORT")
    config: dict[str, object] = {}

    for key in keys:
        env_value = os.getenv(f"{prefix}_{key}")
        if env_value:
            config[key] = env_value

    engine = _normalise_engine_name(os.getenv(f"{prefix}_ENGINE"))
    if engine:
        config["ENGINE"] = engine
    elif config:
        # Assume PostgreSQL when connection components are provided but the
        # engine is omitted. This mirrors the project's deployment defaults.
        config["ENGINE"] = "django.db.backends.postgresql"

    options = _load_options_from_env(f"{prefix}_OPTIONS")
    if options:
        config["OPTIONS"] = options

    if not config.get("ENGINE") or not config.get("NAME"):
        return None

    config["CONN_MAX_AGE"] = conn_max_age
    return config


def _find_component_config(
    prefixes: Sequence[str],
    *,
    conn_max_age: int,
) -> dict[str, object] | None:
    """Return the first component-based database config that resolves."""

    for prefix in prefixes:
        component = _build_component_config(prefix, conn_max_age=conn_max_age)
        if component:
            return component
    return None


def build_database_config(
    primary_env_var: str,
    *,
    fallback_env_vars: Sequence[str] | None = None,
    default_url: str | None = None,
    test_env_vars: Sequence[str] | None = None,
    conn_max_age: int = 600,
) -> dict[str, object]:
    """Build a Django database configuration driven by environment variables."""

    fallback_env_vars = fallback_env_vars or ()
    test_env_vars = test_env_vars or ()

    host_suffix_candidates = [
        f"{primary_env_var}_HOST_SUFFIX",
        *[f"{candidate}_HOST_SUFFIX" for candidate in fallback_env_vars],
        "DATABASE_HOST_SUFFIX",
    ]

    host_suffix = _first_env_value(host_suffix_candidates)

    use_test_database = bool(
        os.getenv("PYTEST_CURRENT_TEST") or os.getenv("DJANGO_USE_TEST_DATABASE")
    )

    database_url = os.getenv(primary_env_var)
    if not database_url:
        for candidate_var in fallback_env_vars:
            database_url = os.getenv(candidate_var)
            if database_url:
                break
    if not database_url:
        component_prefixes = [
            _component_prefix_from_env_var(primary_env_var),
            *[_component_prefix_from_env_var(candidate) for candidate in fallback_env_vars],
        ]
        component_config = _find_component_config(
            component_prefixes,
            conn_max_age=conn_max_age,
        )

        if component_config:
            if host_suffix:
                _apply_host_suffix(component_config, host_suffix)

            test_component = _find_component_config(
                [_component_prefix_from_env_var(candidate) for candidate in test_env_vars],
                conn_max_age=0,
            )

            if test_component:
                if host_suffix:
                    _apply_host_suffix(test_component, host_suffix)
                if use_test_database:
                    return test_component
                component_config["TEST"] = _build_test_settings(test_component)

            return component_config

        database_url = default_url
    if not database_url:
        raise ImproperlyConfigured(
            "A database connection string is required."
        )

    test_url: str | None = None
    for candidate in test_env_vars:
        test_url = os.getenv(candidate)
        if test_url:
            break

    if use_test_database and test_url:
        parsed = dj_database_url.parse(test_url, conn_max_age=0)
        return parsed

    parsed = dj_database_url.parse(database_url, conn_max_age=conn_max_age)
    if host_suffix:
        _apply_host_suffix(parsed, host_suffix)
    component_test_config = None
    if not test_url:
        component_test_config = _find_component_config(
            [_component_prefix_from_env_var(candidate) for candidate in test_env_vars],
            conn_max_age=0,
        )
        if component_test_config and host_suffix:
            _apply_host_suffix(component_test_config, host_suffix)
        if use_test_database and component_test_config:
            return component_test_config
    if test_url:
        parsed["TEST"] = _build_test_settings(
            dj_database_url.parse(test_url, conn_max_age=0)
        )
        if host_suffix:
            _apply_host_suffix(parsed["TEST"], host_suffix)
    elif component_test_config:
        parsed["TEST"] = _build_test_settings(component_test_config)
    return parsed


DATABASES = {
    'default': build_database_config(
        'DATABASE_URL',
        default_url='sqlite:///db.sqlite3',
        test_env_vars=(
            'TEST_DATABASE_URL',
        ),
    )
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

SECURITY_ALERT_EMAIL_RECIPIENTS = tuple(
    _split_env_set("SECURITY_ALERT_EMAIL_RECIPIENTS")
)
SECURITY_ALERT_EMAIL_SENDER = os.getenv(
    "SECURITY_ALERT_EMAIL_SENDER",
    DEFAULT_FROM_EMAIL,
)
SECURITY_ALERT_EMAIL_SUBJECT_PREFIX = os.getenv(
    "SECURITY_ALERT_EMAIL_SUBJECT_PREFIX",
    "Security",
)
SECURITY_ALERT_SLACK_WEBHOOK = os.getenv("SECURITY_ALERT_SLACK_WEBHOOK", "")
SECURITY_ALERT_LOGIN_FAILURE_THRESHOLD = int(
    os.getenv("SECURITY_ALERT_LOGIN_FAILURE_THRESHOLD", "5")
)
_critical_action_env = _split_env_set("SECURITY_ALERT_CRITICAL_ACTIONS")
DEFAULT_SECURITY_CRITICAL_ACTIONS = {
    "certificate_revoked",
}
SECURITY_ALERT_CRITICAL_ACTIONS = (
    _critical_action_env if _critical_action_env else DEFAULT_SECURITY_CRITICAL_ACTIONS
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
if not JWT_AUTH_SECRET:
    fallback_secret = os.getenv("DJANGO_SECRET_KEY") or os.getenv("SECRET_KEY")
    if fallback_secret:
        JWT_AUTH_SECRET = fallback_secret
    else:  # Default to the development key for local usage
        JWT_AUTH_SECRET = get_secret_key(True)
JWT_AUTH_ALGORITHM = os.getenv("JWT_AUTH_ALGORITHM", "HS256")
_jwt_algorithms_env = os.getenv("JWT_AUTH_ALGORITHMS")
JWT_AUTH_ALGORITHMS = (
    tuple(algo.strip() for algo in _jwt_algorithms_env.split(",") if algo.strip())
    if _jwt_algorithms_env
    else None
)
