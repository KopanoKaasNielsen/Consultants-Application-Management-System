"""Background tasks for decision side effects."""
from __future__ import annotations

from typing import Callable

from apps.certificates.services import (
    generate_approval_certificate,
    generate_rejection_letter,
)
from apps.consultants.models import Consultant
from consultant_app.models import Certificate
from .emails import send_decision_email

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


@shared_task(name="decisions.generate_approval_certificate")
def generate_approval_certificate_task(consultant_id: int, generated_by: str | None = None):
    consultant = Consultant.objects.get(pk=consultant_id)
    generate_approval_certificate(consultant, generated_by=generated_by)
    certificate = Certificate.objects.latest_for_consultant(consultant)
    if certificate:
        from consultant_app.tasks.notifications import send_certificate_notification

        send_certificate_notification.delay(
            consultant.pk,
            event="issued",
            certificate_id=certificate.pk,
            metadata={
                "source": "decisions.generate_approval_certificate",
                "generated_by": generated_by,
            },
        )
    send_decision_email_task.delay(consultant_id, "approved")


@shared_task(name="decisions.generate_rejection_letter")
def generate_rejection_letter_task(consultant_id: int, generated_by: str | None = None):
    consultant = Consultant.objects.get(pk=consultant_id)
    generate_rejection_letter(consultant, generated_by=generated_by)
    send_decision_email_task.delay(consultant_id, "rejected")


@shared_task(name="decisions.send_decision_email")
def send_decision_email_task(consultant_id: int, action: str):
    consultant = Consultant.objects.get(pk=consultant_id)
    send_decision_email(consultant, action)
