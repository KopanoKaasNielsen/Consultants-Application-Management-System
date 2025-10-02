"""Helper functions for sending decision outcome emails."""

from __future__ import annotations

from typing import Optional

from django.conf import settings
from django.core.mail import EmailMessage

from apps.consultants.models import Consultant


def _default_from_email() -> str:
    return getattr(settings, "DEFAULT_FROM_EMAIL", None) or "no-reply@example.com"


def send_decision_email(consultant: Consultant, action: str) -> Optional[int]:
    """
    Send an email to the consultant notifying them of the decision outcome.

    Parameters
    ----------
    consultant:
        The consultant whose application decision is being communicated.
    action:
        The decision that was taken. Currently only "approved" and "rejected"
        trigger emails.

    Returns
    -------
    Optional[int]
        The number of successfully delivered messages, as returned by
        ``EmailMessage.send``. ``None`` is returned when the action does not
        trigger an email.
    """

    action = action.lower()
    if action not in {"approved", "rejected"}:
        return None

    if action == "approved":
        subject = "Your consultant application has been approved"
        body_lines = [
            f"Hello {consultant.full_name},",
            "",
            "We are pleased to inform you that your consultant application has been approved.",
            "Please find your approval certificate attached for your records.",
        ]
        attachment_field = consultant.certificate_pdf
    else:  # action == "rejected"
        subject = "Update on your consultant application"
        body_lines = [
            f"Hello {consultant.full_name},",
            "",
            "Thank you for your interest in working with us. After careful review, your application has been declined at this time.",
            "Please review the attached letter for additional details.",
        ]
        attachment_field = consultant.rejection_letter

    body_lines.extend(
        [
            "",
            "If you have any questions, please reply to this email.",
            "",
            "Regards,",
            "Consultant Applications Team",
        ]
    )

    message = "\n".join(body_lines)
    email = EmailMessage(
        subject=subject,
        body=message,
        from_email=_default_from_email(),
        to=[consultant.email],
    )

    if attachment_field:
        attachment_field.open("rb")
        try:
            filename = attachment_field.name.rsplit("/", 1)[-1]
            email.attach(filename, attachment_field.read(), "application/pdf")
        finally:
            attachment_field.close()

    return email.send(fail_silently=False)

