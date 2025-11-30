"""Production settings for the backend project."""

from __future__ import annotations

from django.conf import global_settings

from .base import *  # noqa: F401,F403
from .base import (
    BASE_DIR,
    build_allowed_hosts,
    build_database_config,
    get_csrf_trusted_origins,
    get_env_bool,
    get_secret_key,
)

DEBUG = get_env_bool("DJANGO_DEBUG", default=False)

SECRET_KEY = get_secret_key(DEBUG)

STATICFILES_DIRS = [BASE_DIR / "static"]

ALLOWED_HOSTS = build_allowed_hosts(
    "PROD_ALLOWED_HOSTS",
    "ALLOWED_HOSTS",
    default=(".onrender.com",),
)

CSRF_TRUSTED_ORIGINS = get_csrf_trusted_origins(
    "PROD_CSRF_TRUSTED_ORIGINS",
    default=("https://cams-prod.onrender.com",),
)

DATABASES["default"] = build_database_config(
    "PROD_DATABASE_URL",
    fallback_env_vars=("DATABASE_URL",),
    test_env_vars=("PROD_TEST_DATABASE_URL", "TEST_DATABASE_URL"),
    conn_max_age=600,
)

STORAGES = {
    **getattr(global_settings, "STORAGES", {}),
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
