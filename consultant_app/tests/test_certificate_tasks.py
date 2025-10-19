import pytest
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.utils import timezone

from apps.consultants.models import Consultant, Notification
from consultant_app.certificates import (
    CertificateTokenError,
    build_certificate_token,
    verify_certificate_token,
)
from consultant_app.models import Certificate
from consultant_app.tasks import (
    reissue_certificate_task,
    revoke_certificate_task,
)


@pytest.fixture
def temporary_media_root(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


@pytest.fixture
def consultant_with_live_certificate(db, temporary_media_root):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="cert-task-user",
        email="cert-task@example.com",
        password="secure-pass-123",
    )

    consultant = Consultant.objects.create(
        user=user,
        full_name="Task Runner",
        id_number="TASK-001",
        dob=timezone.now().date(),
        gender="M",
        nationality="Kenya",
        email="cert-task@example.com",
        phone_number="0700000000",
        business_name="Task Testing",
        registration_number="REG-001",
        status="approved",
        submitted_at=timezone.now(),
    )

    issued_at = timezone.now()
    consultant.certificate_generated_at = issued_at
    consultant.certificate_expires_at = timezone.localdate()
    consultant.save(
        update_fields=[
            "certificate_generated_at",
            "certificate_expires_at",
        ]
    )

    consultant.certificate_pdf.save("initial.pdf", ContentFile(b"%PDF-1.4"), save=True)

    certificate = Certificate.objects.create(
        consultant=consultant,
        status=Certificate.Status.VALID,
        issued_at=issued_at,
        status_set_at=issued_at,
        valid_at=issued_at,
    )

    yield consultant, certificate

    consultant.refresh_from_db()
    if consultant.certificate_pdf:
        consultant.certificate_pdf.delete(save=False)


@pytest.mark.django_db
def test_revoke_certificate_task_updates_status(consultant_with_live_certificate):
    consultant, certificate = consultant_with_live_certificate
    token = build_certificate_token(consultant)

    revoke_certificate_task(
        consultant.pk,
        reason="Revoked for compliance",
        actor_id=None,
        notify_consultant=False,
    )

    certificate.refresh_from_db()
    assert certificate.status == Certificate.Status.REVOKED
    assert certificate.status_reason == "Revoked for compliance"
    assert certificate.revoked_at is not None

    with pytest.raises(CertificateTokenError) as exc:
        verify_certificate_token(token, consultant)

    assert str(exc.value) == "Certificate has been revoked."


@pytest.mark.django_db
def test_reissue_certificate_task_regenerates_certificate(consultant_with_live_certificate):
    consultant, previous_certificate = consultant_with_live_certificate
    original_token = build_certificate_token(consultant)

    reissue_certificate_task(
        consultant.pk,
        reason="Updated profile information",
        actor_id=None,
        notify_consultant=False,
    )

    consultant.refresh_from_db()
    previous_certificate.refresh_from_db()
    assert previous_certificate.status == Certificate.Status.REISSUED
    assert previous_certificate.status_reason == "Updated profile information"

    new_certificate = Certificate.objects.latest_for_consultant(consultant)
    assert new_certificate.pk != previous_certificate.pk
    assert new_certificate.status == Certificate.Status.VALID
    assert consultant.certificate_generated_at == new_certificate.issued_at
    assert consultant.certificate_pdf
    assert consultant.certificate_pdf.name.endswith(
        f"approval-certificate-{consultant.pk}.pdf"
    )

    new_token = build_certificate_token(consultant)
    assert new_token != original_token

    with pytest.raises(CertificateTokenError):
        verify_certificate_token(original_token, consultant)


@pytest.mark.django_db
def test_certificate_tasks_dispatch_notifications(consultant_with_live_certificate, mocker):
    consultant, _ = consultant_with_live_certificate
    Notification.objects.all().delete()
    mocked_delay = mocker.patch(
        "consultant_app.tasks.notifications.send_certificate_notification.delay"
    )

    revoke_certificate_task(
        consultant.pk,
        reason="Notification check",
        actor_id=None,
        notify_consultant=True,
    )

    reissue_certificate_task(
        consultant.pk,
        reason="Reissue notification",
        actor_id=None,
        notify_consultant=True,
    )

    notifications = Notification.objects.filter(recipient=consultant.user).order_by(
        "created_at"
    )
    assert notifications.count() == 2
    messages = [entry.message for entry in notifications]
    assert any("revoked" in message.lower() for message in messages)
    assert any("reissued" in message.lower() for message in messages)
    events = [call.kwargs.get("event") for call in mocked_delay.call_args_list]
    assert events.count("revoked") == 1
    assert events.count("reissued") == 1
