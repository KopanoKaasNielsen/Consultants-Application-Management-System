from django.conf import settings
from django.core.mail import send_mail
from django.utils.translation import gettext_lazy as _


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

    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None) or "no-reply@example.com"

    send_mail(
        subject,
        message,
        from_email,
        [consultant.email],
        fail_silently=False,
    )
