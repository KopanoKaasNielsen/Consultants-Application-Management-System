from __future__ import annotations

"""
Development settings for the backend project.
This configuration targets local or AIX-mimic environments
running PostgreSQL 15+. SQLite fallback is disabled.
"""

import os
import sys
import logging
import environ

from .base import *  # noqa: F401,F403

# Explicit re-export for tools that expect these helpers to be available directly
# within the dev settings module. ``import *`` above ensures core settings such as
# ``ROOT_URLCONF`` are defined, while the names below keep IDE type checking happy
# and make their usage obvious in this file.
from .base import (  # noqa: F401,F403
    BASE_DIR,
    build_allowed_hosts,
    build_database_config,
    get_csrf_trusted_origins,
    get_env_bool,
    get_env_int,
    get_secret_key,
)

# ---------------------------------------------------------------------------
# Environment Setup
# ---------------------------------------------------------------------------

# Ensure BASE_DIR is on sys.path so imports remain consistent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

pythonpath = os.environ.get("PYTHONPATH", "")
pythonpath_parts = [path for path in pythonpath.split(os.pathsep) if path]
if str(BASE_DIR) not in pythonpath_parts:
    pythonpath_parts.insert(0, str(BASE_DIR))
    os.environ["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)

# Always define the dev settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings.dev")

# Load environment variables from .env at project root
env = environ.Env()
environ.Env.read_env(os.path.join(BASE_DIR, ".env"))

# ---------------------------------------------------------------------------
# Core Django Settings
# ---------------------------------------------------------------------------

DEBUG = get_env_bool("DJANGO_DEBUG", default=True)
SECRET_KEY = get_secret_key(DEBUG)

# Serve static files directly from the “static” directory during dev
STATICFILES_DIRS = [BASE_DIR / "static"]
STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"

ALLOWED_HOSTS = build_allowed_hosts(
    "DEV_ALLOWED_HOSTS",
    "ALLOWED_HOSTS",
    default=("localhost", "127.0.0.1"),
)

CSRF_TRUSTED_ORIGINS = get_csrf_trusted_origins(
    "DEV_CSRF_TRUSTED_ORIGINS",
    default=("http://localhost", "http://127.0.0.1"),
)

# ---------------------------------------------------------------------------
# Database (PostgreSQL only)
# ---------------------------------------------------------------------------

DATABASES = {}
DATABASES["default"] = build_database_config(
    "DEV_DATABASE_URL",
    fallback_env_vars=("DATABASE_URL",),
    default_url=None,  # Disable SQLite fallback
    test_env_vars=("DEV_TEST_DATABASE_URL", "TEST_DATABASE_URL"),
)
DATABASES["default"].setdefault("TEST", {})
DATABASES["default"]["TEST"].setdefault("SERIALIZE", False)

# Diagnostic log to confirm active DB engine
_active_db = DATABASES["default"]
logging.warning(
    "Using database engine: %s | Name: %s | Host: %s | Port: %s",
    _active_db.get("ENGINE"),
    _active_db.get("NAME"),
    _active_db.get("HOST"),
    _active_db.get("PORT"),
)

# ---------------------------------------------------------------------------
# Security / SSL Flags
# ---------------------------------------------------------------------------

SECURE_SSL_REDIRECT = get_env_bool("DJANGO_SECURE_SSL_REDIRECT", default=False)
SESSION_COOKIE_SECURE = get_env_bool("DJANGO_SESSION_COOKIE_SECURE", default=False)
CSRF_COOKIE_SECURE = get_env_bool("DJANGO_CSRF_COOKIE_SECURE", default=False)
SECURE_HSTS_SECONDS = get_env_int("DJANGO_SECURE_HSTS_SECONDS", default=0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = get_env_bool(
    "DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", default=False
)
SECURE_HSTS_PRELOAD = get_env_bool("DJANGO_SECURE_HSTS_PRELOAD", default=False)
