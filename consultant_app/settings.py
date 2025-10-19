"""Celery configuration helpers for the simplified consultant app."""
from __future__ import annotations

import os
from typing import Final

from celery.schedules import crontab


def _get_env_bool(name: str, default: bool = False) -> bool:
    """Return a boolean representation for an environment variable."""

    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _split_env_list(name: str) -> list[str]:
    """Return a list of comma separated environment variable values."""

    raw_value = os.getenv(name, "")
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def _parse_crontab(name: str, default_spec: str):
    """Return a Celery crontab schedule from an env var."""

    value = os.getenv(name, default_spec)
    parts = value.split()
    if len(parts) != 5:
        parts = default_spec.split()
    minute, hour, day_of_month, month_of_year, day_of_week = parts
    return crontab(
        minute=minute,
        hour=hour,
        day_of_month=day_of_month,
        month_of_year=month_of_year,
        day_of_week=day_of_week,
    )


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

ADMIN_REPORT_RECIPIENTS: Final[tuple[str, ...]] = tuple(
    _split_env_list("ADMIN_REPORT_RECIPIENTS")
)
ADMIN_REPORT_FROM_EMAIL: Final[str] = os.getenv(
    "ADMIN_REPORT_FROM_EMAIL", os.getenv("DEFAULT_FROM_EMAIL", "no-reply@example.com")
)
_DEFAULT_BASE_URL = os.getenv("REPORT_BASE_URL") or os.getenv("SITE_BASE_URL") or "http://localhost:8000/"
ADMIN_REPORT_BASE_URL: Final[str] = os.getenv(
    "ADMIN_REPORT_BASE_URL",
    _DEFAULT_BASE_URL,
)
ADMIN_REPORT_ATTACHMENT_PREFIX: Final[str] = os.getenv(
    "ADMIN_REPORT_ATTACHMENT_PREFIX",
    "consultant-analytics",
)
ADMIN_REPORT_SUBJECTS: Final[dict[str, str]] = {
    "weekly": os.getenv(
        "ADMIN_REPORT_WEEKLY_SUBJECT",
        "Weekly consultant analytics report",
    ),
    "monthly": os.getenv(
        "ADMIN_REPORT_MONTHLY_SUBJECT",
        "Monthly consultant analytics report",
    ),
    "manual": os.getenv(
        "ADMIN_REPORT_MANUAL_SUBJECT",
        "Consultant analytics report",
    ),
}

ADMIN_REPORT_WEEKLY_SCHEDULE = _parse_crontab(
    "ADMIN_REPORT_WEEKLY_CRON", "0 6 * * MON"
)
ADMIN_REPORT_MONTHLY_SCHEDULE = _parse_crontab(
    "ADMIN_REPORT_MONTHLY_CRON", "0 7 1 * *"
)

CELERY_BEAT_SCHEDULE: Final[dict[str, dict[str, object]]] = {
    "consultant_app.send_weekly_admin_report": {
        "task": "consultant_app.tasks.scheduled_reports.send_weekly_admin_report",
        "schedule": ADMIN_REPORT_WEEKLY_SCHEDULE,
    },
    "consultant_app.send_monthly_admin_report": {
        "task": "consultant_app.tasks.scheduled_reports.send_monthly_admin_report",
        "schedule": ADMIN_REPORT_MONTHLY_SCHEDULE,
    },
}

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
    "ADMIN_REPORT_RECIPIENTS",
    "ADMIN_REPORT_FROM_EMAIL",
    "ADMIN_REPORT_BASE_URL",
    "ADMIN_REPORT_ATTACHMENT_PREFIX",
    "ADMIN_REPORT_SUBJECTS",
    "ADMIN_REPORT_WEEKLY_SCHEDULE",
    "ADMIN_REPORT_MONTHLY_SCHEDULE",
    "CELERY_BEAT_SCHEDULE",
]
