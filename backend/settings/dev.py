"""Development settings for the backend project."""

from __future__ import annotations

import os
import sys

from .base import *  # noqa: F401,F403
from .base import (
    BASE_DIR,
    build_allowed_hosts,
    build_database_config,
    get_csrf_trusted_origins,
    get_env_bool,
    get_secret_key,
)

# Ensure the repository root is on ``sys.path`` and reflected in ``PYTHONPATH`` so
# imports work consistently in local environments and CI.
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

pythonpath = os.environ.get("PYTHONPATH", "")
pythonpath_parts = [path for path in pythonpath.split(os.pathsep) if path]
if str(BASE_DIR) not in pythonpath_parts:
    pythonpath_parts.insert(0, str(BASE_DIR))
    os.environ["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings.dev")

DEBUG = get_env_bool("DJANGO_DEBUG", default=True)

SECRET_KEY = get_secret_key(DEBUG)

STATICFILES_DIRS = [BASE_DIR / 'static']

ALLOWED_HOSTS = build_allowed_hosts(
    "DEV_ALLOWED_HOSTS",
    "ALLOWED_HOSTS",
    default=("localhost", "127.0.0.1"),
)

CSRF_TRUSTED_ORIGINS = get_csrf_trusted_origins(
    "DEV_CSRF_TRUSTED_ORIGINS",
    default=("http://localhost", "http://127.0.0.1"),
)

DATABASES["default"] = build_database_config(
    "DEV_DATABASE_URL",
    fallback_env_vars=("DATABASE_URL",),
    default_url="sqlite:///db.sqlite3",
    test_env_vars=("DEV_TEST_DATABASE_URL", "TEST_DATABASE_URL"),
)
