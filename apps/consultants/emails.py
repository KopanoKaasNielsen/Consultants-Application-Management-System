from django.conf import settings
from django.core.mail import send_mail
from django.utils.translation import gettext_lazy as _


def _default_from_email() -> str:
    return getattr(settings, "DEFAULT_FROM_EMAIL", None) or "no-reply@example.com"


def send_submission_confirmation_email(consultant):
    """Send a confirmation email to the consultant after submission."""
    subject = _("Consultant Application Submitted")
    message_lines = [
        _("Hello {name},").format(name=consultant.full_name),
        "",
        _("Thank you for submitting your consultant application."),
        _("We have received the following details:"),
        f" - {_('Full Name')}: {consultant.full_name}",
        f" - {_('Business Name')}: {consultant.business_name}",
        f" - {_('Registration Number')}: {consultant.registration_number or _('N/A')}",
        (
            f" - {_('Submitted At')}: {consultant.submitted_at:%Y-%m-%d %H:%M %Z}"
            if consultant.submitted_at
            else ""
        ),
        "",
        _("Our team will review your application and contact you with any updates."),
    ]
    message = "\n".join(str(line) for line in message_lines if line)

    send_mail(
        subject,
        message,
        _default_from_email(),
        [consultant.email],
        fail_silently=False,
    )


def send_status_update_email(consultant, action: str, comment: str = "") -> None:
    """Send a status update email when staff take a decision."""

    action = (action or "").lower()
    if action not in {"approved", "rejected"}:
        return

    if action == "approved":
        subject = _("Your consultant application has been approved")
        message_lines = [
            _("Hello {name},").format(name=consultant.full_name),
            "",
            _("Great news! Your consultant application has been approved."),
        ]
    else:
        subject = _("Update on your consultant application")
        message_lines = [
            _("Hello {name},").format(name=consultant.full_name),
            "",
            _("Thank you for your application. After review, we are unable to approve it at this time."),
        ]
        if comment:
            message_lines.extend(["", _("Notes from our team:"), comment])

    message_lines.extend([
        "",
        _("You can view the latest details from your consultant dashboard."),
        "",
        _("Regards,"),
        _("Consultant Applications Team"),
    ])

    send_mail(
        subject,
        "\n".join(str(line) for line in message_lines if line is not None),
        _default_from_email(),
        [consultant.email],
        fail_silently=False,
    )
