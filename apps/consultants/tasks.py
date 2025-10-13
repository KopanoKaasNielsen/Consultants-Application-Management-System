"""Background tasks for consultant workflows."""
from __future__ import annotations

import logging
from typing import Callable

from django.db import transaction

from .emails import send_submission_confirmation_email
from .models import Consultant

logger = logging.getLogger(__name__)


try:  # pragma: no cover - exercised implicitly when Celery is installed
    from celery import shared_task
except ModuleNotFoundError:  # pragma: no cover - provides a fallback in tests
    def shared_task(*dargs, **dkwargs):
        def decorator(func: Callable):
            def delay(*args, **kwargs):
                return func(*args, **kwargs)

            func.delay = delay  # type: ignore[attr-defined]
            return func

        if dargs and callable(dargs[0]) and not dkwargs:
            return decorator(dargs[0])
        return decorator


@shared_task(name="consultants.send_submission_confirmation_email")
def send_submission_confirmation_email_task(consultant_id: int) -> None:
    """Send a confirmation email after ensuring the consultant exists."""

    try:
        consultant = Consultant.objects.select_related("user").get(pk=consultant_id)
    except Consultant.DoesNotExist:  # pragma: no cover - defensive guard
        logger.warning(
            "Consultant %s disappeared before confirmation email could be sent.",
            consultant_id,
            extra={
                "consultant_id": consultant_id,
                "context": {
                    "action": "submission_confirmation_email.missing",
                    "consultant_id": consultant_id,
                },
            },
        )
        return

    # When executed asynchronously we may run outside the request/response
    # transaction; guard by reloading the submitted_at timestamp.
    if consultant.submitted_at is None:
        with transaction.atomic():
            consultant = Consultant.objects.select_for_update().get(pk=consultant_id)
            if consultant.submitted_at is None:
                consultant.submitted_at = consultant.updated_at
                consultant.save(update_fields=["submitted_at", "updated_at"])

    try:
        send_submission_confirmation_email(consultant)
    except Exception:  # pragma: no cover - logged for observability
        logger.exception(
            "Failed to send submission confirmation email for consultant %s",
            consultant_id,
            extra={
                "consultant_id": consultant_id,
                "user_id": consultant.user_id,
                "context": {
                    "action": "submission_confirmation_email.error",
                    "consultant_id": consultant_id,
                    "user_id": consultant.user_id,
                },
            },
        )
        return

    logger.info(
        "Submission confirmation email sent for consultant %s",
        consultant_id,
        extra={
            "consultant_id": consultant_id,
            "user_id": consultant.user_id,
            "context": {
                "action": "submission_confirmation_email.sent",
                "consultant_id": consultant_id,
                "user_id": consultant.user_id,
            },
        },
    )
