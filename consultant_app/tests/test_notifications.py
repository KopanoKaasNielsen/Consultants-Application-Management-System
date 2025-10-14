import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.utils import timezone

from apps.consultants.models import Consultant, LogEntry
from consultant_app.models import Certificate
from consultant_app.tasks.notifications import (
    NotificationDeliveryError,
    send_certificate_notification,
)


@pytest.fixture
def consultant_certificate(db):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="notify-user",
        email="notify@example.com",
        password="secure-pass-123",
    )
    consultant = Consultant.objects.create(
        user=user,
        full_name="Notify Me",
        id_number="NOTIFY-001",
        dob=timezone.now().date(),
        gender="F",
        nationality="Kenya",
        email="notify@example.com",
        phone_number="0712345678",
        business_name="Notification Experts",
        registration_number="REG-900",
        status="approved",
        submitted_at=timezone.now(),
    )
    issued_at = timezone.now()
    certificate = Certificate.objects.create(
        consultant=consultant,
        status=Certificate.Status.VALID,
        issued_at=issued_at,
        status_set_at=issued_at,
        valid_at=issued_at,
    )
    return consultant, certificate


@pytest.mark.django_db
def test_send_certificate_notification_sends_email_and_sms(
    settings, mocker, consultant_certificate
):
    consultant, certificate = consultant_certificate
    LogEntry.objects.all().delete()
    mail.outbox.clear()

    settings.DEFAULT_FROM_EMAIL = "team@example.com"
    settings.CERTIFICATE_NOTIFICATION_ENABLE_SMS = True
    mock_sms = mocker.patch(
        "consultant_app.tasks.notifications._dispatch_sms", return_value=True
    )

    result = send_certificate_notification.apply(
        args=(consultant.pk,),
        kwargs={
            "event": "issued",
            "certificate_id": certificate.pk,
            "reason": "Issued after approval",
            "metadata": {"source": "pytest"},
        },
    ).get()

    assert result == {"email": "sent", "sms": "sent"}
    assert mail.outbox, "Expected an email to be sent"
    delivered_email = mail.outbox[-1]
    assert consultant.full_name in delivered_email.body
    assert "certificate" in delivered_email.subject.lower()

    mock_sms.assert_called_once()
    sms_args = mock_sms.call_args[0]
    assert consultant.phone_number in sms_args[0]

    entries = LogEntry.objects.filter(context__action="certificate.notification.issued")
    assert entries.count() >= 2  # email + sms entries
    channels = {entry.context.get("channel") for entry in entries}
    assert {"email", "sms"}.issubset(channels)


@pytest.mark.django_db
def test_send_certificate_notification_logs_sms_failure(
    settings, mocker, consultant_certificate
):
    consultant, certificate = consultant_certificate
    LogEntry.objects.all().delete()
    mail.outbox.clear()

    settings.DEFAULT_FROM_EMAIL = "team@example.com"
    settings.CERTIFICATE_NOTIFICATION_ENABLE_SMS = True
    mocker.patch(
        "consultant_app.tasks.notifications._dispatch_sms",
        side_effect=RuntimeError("gateway down"),
    )

    result = send_certificate_notification.apply(
        args=(consultant.pk,),
        kwargs={
            "event": "reissued",
            "certificate_id": certificate.pk,
            "reason": "Details updated",
        },
    ).get()

    assert result["email"] == "sent"
    assert result["sms"] == "failed"

    failure_entry = LogEntry.objects.filter(
        context__action="certificate.notification.reissued",
        context__channel="sms",
        context__status="failed",
    ).first()
    assert failure_entry is not None


@pytest.mark.django_db
def test_send_certificate_notification_raises_on_email_failure(
    settings, mocker, consultant_certificate
):
    consultant, certificate = consultant_certificate
    LogEntry.objects.all().delete()
    mail.outbox.clear()

    settings.DEFAULT_FROM_EMAIL = "team@example.com"
    mocker.patch("consultant_app.tasks.notifications.send_mail", side_effect=RuntimeError)

    with pytest.raises(NotificationDeliveryError):
        send_certificate_notification.apply(
            args=(consultant.pk,),
            kwargs={
                "event": "revoked",
                "certificate_id": certificate.pk,
                "reason": "Compliance review",
            },
        )

    failure_entry = LogEntry.objects.filter(
        context__action="certificate.notification.revoked",
        context__channel="email",
        context__status="failed",
    ).first()
    assert failure_entry is not None
