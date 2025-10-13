"""Celery configuration helpers for the simplified consultant app."""
from __future__ import annotations

import os
from typing import Final


def _get_env_bool(name: str, default: bool = False) -> bool:
    """Return a boolean representation for an environment variable."""

    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


CELERY_BROKER_URL: Final[str] = os.getenv(
    "CELERY_BROKER_URL",
    os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"),
)
CELERY_RESULT_BACKEND: Final[str | None] = os.getenv(
    "CELERY_RESULT_BACKEND",
    CELERY_BROKER_URL,
)
CELERY_TASK_DEFAULT_QUEUE: Final[str] = os.getenv(
    "CELERY_TASK_DEFAULT_QUEUE",
    "consultant_app",
)
CELERY_TASK_DEFAULT_EXCHANGE: Final[str] = os.getenv(
    "CELERY_TASK_DEFAULT_EXCHANGE",
    CELERY_TASK_DEFAULT_QUEUE,
)
CELERY_TASK_DEFAULT_ROUTING_KEY: Final[str] = os.getenv(
    "CELERY_TASK_DEFAULT_ROUTING_KEY",
    CELERY_TASK_DEFAULT_QUEUE,
)
CELERY_TASK_ALWAYS_EAGER: Final[bool] = _get_env_bool(
    "CELERY_TASK_ALWAYS_EAGER",
    False,
)
CELERY_TASK_EAGER_PROPAGATES: Final[bool] = _get_env_bool(
    "CELERY_TASK_EAGER_PROPAGATES",
    CELERY_TASK_ALWAYS_EAGER,
)
CELERY_TASK_ACKS_LATE: Final[bool] = _get_env_bool(
    "CELERY_TASK_ACKS_LATE",
    False,
)
CELERY_TASK_SOFT_TIME_LIMIT: Final[int] = int(
    os.getenv("CELERY_TASK_SOFT_TIME_LIMIT", "60")
)
CELERY_TASK_TIME_LIMIT: Final[int] = int(
    os.getenv("CELERY_TASK_TIME_LIMIT", "300")
)

__all__ = [
    "CELERY_BROKER_URL",
    "CELERY_RESULT_BACKEND",
    "CELERY_TASK_DEFAULT_QUEUE",
    "CELERY_TASK_DEFAULT_EXCHANGE",
    "CELERY_TASK_DEFAULT_ROUTING_KEY",
    "CELERY_TASK_ALWAYS_EAGER",
    "CELERY_TASK_EAGER_PROPAGATES",
    "CELERY_TASK_ACKS_LATE",
    "CELERY_TASK_SOFT_TIME_LIMIT",
    "CELERY_TASK_TIME_LIMIT",
]
