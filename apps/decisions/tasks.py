"""Background tasks for decision side effects."""
from __future__ import annotations

from typing import Callable, Optional

from django.contrib.auth import get_user_model

from apps.certificates.services import (
    generate_approval_certificate,
    generate_rejection_letter,
)
from apps.consultants.models import Consultant
from consultant_app.models import Certificate
from .emails import send_decision_email

UserModel = get_user_model()

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
def generate_approval_certificate_task(
    consultant_id: int, generated_by: str | None = None, actor_id: Optional[int] = None
):
    consultant = Consultant.objects.get(pk=consultant_id)
    actor = None
    if actor_id is not None:
        try:
            actor = UserModel.objects.get(pk=actor_id)
        except UserModel.DoesNotExist:
            actor = None
    generate_kwargs: dict[str, object] = {"generated_by": generated_by}
    if actor is not None:
        generate_kwargs["actor"] = actor

    generate_approval_certificate(
        consultant,
        **generate_kwargs,
    )
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
def generate_rejection_letter_task(
    consultant_id: int, generated_by: str | None = None, actor_id: Optional[int] = None
):
    consultant = Consultant.objects.get(pk=consultant_id)
    actor = None
    if actor_id is not None:
        try:
            actor = UserModel.objects.get(pk=actor_id)
        except UserModel.DoesNotExist:
            actor = None
    generate_kwargs: dict[str, object] = {"generated_by": generated_by}
    if actor is not None:
        generate_kwargs["actor"] = actor

    generate_rejection_letter(
        consultant,
        **generate_kwargs,
    )
    send_decision_email_task.delay(consultant_id, "rejected")


@shared_task(name="decisions.send_decision_email")
def send_decision_email_task(consultant_id: int, action: str):
    consultant = Consultant.objects.get(pk=consultant_id)
    send_decision_email(consultant, action)
