"""Application bootstrap for Celery integration."""
from __future__ import annotations

from .tasks import celery_app as app

__all__ = ("app",)
