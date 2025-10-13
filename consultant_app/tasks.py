"""Celery tasks for the simplified consultant application."""
from __future__ import annotations

from typing import Any

from celery import Celery, shared_task
from celery.utils.log import get_task_logger
from django.conf import settings

from consultant_app import settings as consultant_settings

celery_app = Celery("consultant_app")
celery_app.config_from_object("django.conf:settings", namespace="CELERY")
celery_app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)
celery_app.conf.update(
    task_default_queue=consultant_settings.CELERY_TASK_DEFAULT_QUEUE,
    task_default_exchange=consultant_settings.CELERY_TASK_DEFAULT_EXCHANGE,
    task_default_routing_key=consultant_settings.CELERY_TASK_DEFAULT_ROUTING_KEY,
)
celery_app.set_default()

logger = get_task_logger(__name__)


def _resolve_consultant(identifier: Any):
    """Resolve a consultant either by primary key or email address."""

    from apps.consultants.models import Consultant

    queryset = Consultant.objects.select_related("user")

    if isinstance(identifier, int):
        return queryset.get(pk=identifier)

    if isinstance(identifier, str):
        candidate = identifier.strip()
        if candidate.isdigit():
            return queryset.get(pk=int(candidate))
        if "@" in candidate:
            try:
                return queryset.get(email__iexact=candidate)
            except Consultant.DoesNotExist:
                return queryset.get(user__email__iexact=candidate)

    raise Consultant.DoesNotExist  # type: ignore[misc]


@shared_task(
    bind=True,
    name="consultant_app.send_confirmation_email",
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=5,
    retry_jitter=True,
    retry_kwargs={"max_retries": 3},
)
def send_confirmation_email(self, consultant_identifier: Any) -> None:
    """Send the consultant submission confirmation email."""

    from apps.consultants.emails import send_submission_confirmation_email
    from apps.consultants.models import Consultant

    try:
        consultant = _resolve_consultant(consultant_identifier)
    except Consultant.DoesNotExist:
        logger.warning(
            "Consultant %s could not be found for confirmation email.",
            consultant_identifier,
        )
        return None

    logger.info(
        "Dispatching confirmation email for consultant %s", consultant.pk
    )

    try:
        send_submission_confirmation_email(consultant)
    except Exception:  # pragma: no cover - ensures retries log context
        logger.exception(
            "Failed to send confirmation email for consultant %s",
            consultant.pk,
        )
        raise

    logger.info("Sent confirmation email for consultant %s", consultant.pk)


__all__ = ["celery_app", "send_confirmation_email"]
