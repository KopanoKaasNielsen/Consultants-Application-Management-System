"""Production settings for the backend project."""

from __future__ import annotations

from django.conf import global_settings

from .base import *  # noqa: F401,F403
from .base import (
    BASE_DIR,
    build_allowed_hosts,
    build_csrf_trusted_origins,
    get_env_bool,
    get_secret_key,
)

DEBUG = get_env_bool("DJANGO_DEBUG", default=False)

SECRET_KEY = get_secret_key(DEBUG)

ALLOWED_HOSTS = build_allowed_hosts(["localhost", "127.0.0.1", "0.0.0.0"])
CSRF_TRUSTED_ORIGINS = build_csrf_trusted_origins(ALLOWED_HOSTS)

STATICFILES_DIRS = [BASE_DIR / "static"]

STORAGES = {
    **getattr(global_settings, "STORAGES", {}),
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
