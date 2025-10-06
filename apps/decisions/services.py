"""Service layer helpers for decision handling."""
from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from django.db import transaction

from apps.consultants.models import Consultant

from .models import ApplicationAction
from .tasks import (
    generate_approval_certificate_task,
    generate_rejection_letter_task,
)

if TYPE_CHECKING:  # pragma: no cover - used for type checkers only
    from django.contrib.auth.models import AbstractBaseUser as User
else:  # pragma: no cover - runtime typing fallback
    from typing import Any as User


def _actor_display_name(actor: User) -> Optional[str]:
    full_name = actor.get_full_name()
    return full_name or getattr(actor, "username", None)


def process_decision_action(
    consultant: Consultant,
    action: str,
    actor: User,
    *,
    notes: str = "",
) -> ApplicationAction:
    """Persist the action, update the consultant, and queue side-effects."""

    generated_by = _actor_display_name(actor)

    with transaction.atomic():
        action_obj = ApplicationAction.objects.create(
            consultant=consultant,
            actor=actor,
            action=action,
            notes=notes,
        )

        update_fields = ["status"]
        new_status = consultant.status

        if action == "vetted":
            new_status = "vetted"
        elif action == "approved":
            new_status = "approved"
            if consultant.certificate_pdf:
                consultant.certificate_pdf.delete(save=False)
            consultant.certificate_pdf = None
            consultant.certificate_generated_at = None
            if consultant.rejection_letter:
                consultant.rejection_letter.delete(save=False)
            consultant.rejection_letter = None
            consultant.rejection_letter_generated_at = None
            consultant.certificate_expires_at = None
            update_fields.extend(
                [
                    "certificate_pdf",
                    "certificate_generated_at",
                    "certificate_expires_at",
                    "rejection_letter",
                    "rejection_letter_generated_at",
                ]
            )
        elif action == "rejected":
            new_status = "rejected"
            if consultant.rejection_letter:
                consultant.rejection_letter.delete(save=False)
            consultant.rejection_letter = None
            consultant.rejection_letter_generated_at = None
            if consultant.certificate_pdf:
                consultant.certificate_pdf.delete(save=False)
            consultant.certificate_pdf = None
            consultant.certificate_generated_at = None
            consultant.certificate_expires_at = None
            update_fields.extend(
                [
                    "rejection_letter",
                    "rejection_letter_generated_at",
                    "certificate_pdf",
                    "certificate_generated_at",
                    "certificate_expires_at",
                ]
            )

        consultant.status = new_status
        consultant.save(update_fields=update_fields)

    # Queue follow-up tasks after the database changes have been persisted. We
    # invoke them immediately so that callers running inside an outer atomic
    # block (such as our tests) still see the side-effects, instead of waiting
    # for a later on_commit hook that might never run in that context.
    if action == "approved":
        generate_approval_certificate_task.delay(consultant.pk, generated_by)
    elif action == "rejected":
        generate_rejection_letter_task.delay(consultant.pk, generated_by)
    elif action == "vetted":
        # No side-effects besides the status change.
        pass

    return action_obj
