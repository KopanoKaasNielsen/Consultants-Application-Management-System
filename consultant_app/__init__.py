"""Application bootstrap for Celery integration."""
from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = ("app",)


def __getattr__(name: str) -> Any:
    if name != "app":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module = import_module("consultant_app.tasks")
    return module.celery_app
