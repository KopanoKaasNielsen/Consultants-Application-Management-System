"""Development settings for the backend project."""

from __future__ import annotations

from .base import *  # noqa: F401,F403
from .base import BASE_DIR, get_env_bool, get_secret_key

DEBUG = get_env_bool("DJANGO_DEBUG", default=True)

SECRET_KEY = get_secret_key(DEBUG)

STATICFILES_DIRS = [BASE_DIR / 'static']
