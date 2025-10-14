from __future__ import annotations

import uuid
from datetime import timedelta
from io import BytesIO

import pytest
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from apps.consultants.models import Consultant
from consultant_app.models import Certificate
from consultant_app.certificates import (
    CertificateTokenError,
    build_certificate_token,
    build_verification_url,
    update_certificate_status,
    verify_certificate_token,
)
from utils.qr_generator import generate_qr_code


@pytest.fixture
def consultant_with_certificate(db):
    user = get_user_model().objects.create_user(
        username="verified", email="verified@example.com", password="testpass123"
    )

    consultant = Consultant.objects.create(
        user=user,
        full_name="Verified Consultant",
        id_number="ID-123",
        dob=timezone.now().date(),
        gender="M",
        nationality="Kenya",
        email="verified@example.com",
        phone_number="0700000000",
        business_name="Verified Business",
        registration_number="REG-123",
        status="approved",
        submitted_at=timezone.now(),
    )

    consultant.certificate_generated_at = timezone.now()
    consultant.certificate_expires_at = timezone.localdate()
    consultant.save(
        update_fields=[
            "certificate_generated_at",
            "certificate_expires_at",
        ]
    )
    consultant.certificate_pdf.save(
        "certificate.pdf", ContentFile(b"%PDF-1.4"), save=True
    )

    Certificate.objects.create(
        consultant=consultant,
        status=Certificate.Status.VALID,
        issued_at=consultant.certificate_generated_at,
        status_set_at=consultant.certificate_generated_at,
        valid_at=consultant.certificate_generated_at,
    )

    consultant.refresh_from_db()
    assert consultant.certificate_uuid is not None
    return consultant


@pytest.mark.django_db
def test_generate_qr_code_returns_image():
    image = generate_qr_code("https://example.com/verify")
    assert isinstance(image, Image.Image)

    buffer = BytesIO()
    image.save(buffer, format="PNG")
    assert buffer.tell() > 0


@pytest.mark.django_db
def test_certificate_token_round_trip(consultant_with_certificate):
    consultant = consultant_with_certificate
    token = build_certificate_token(consultant)
    metadata = verify_certificate_token(token, consultant)

    assert metadata.consultant_id == consultant.pk
    assert metadata.issued_at == consultant.certificate_generated_at.isoformat()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "status,error_message",
    (
        (Certificate.Status.REVOKED, "Certificate has been revoked."),
        (Certificate.Status.EXPIRED, "Certificate has expired."),
        (Certificate.Status.REISSUED, "Token is no longer valid for this certificate."),
    ),
)
def test_certificate_token_rejects_inactive_statuses(
    consultant_with_certificate, status, error_message
):
    consultant = consultant_with_certificate
    token = build_certificate_token(consultant)

    certificate = Certificate.objects.latest_for_consultant(consultant)
    certificate.mark_status(status.value, timestamp=timezone.now(), reason=f"{status.label} test")

    with pytest.raises(CertificateTokenError) as exc:
        verify_certificate_token(token, consultant)

    assert str(exc.value) == error_message


@pytest.mark.django_db
def test_certificate_token_double_revoke_remains_blocked(consultant_with_certificate):
    consultant = consultant_with_certificate
    token = build_certificate_token(consultant)

    certificate = Certificate.objects.latest_for_consultant(consultant)
    update_certificate_status(
        consultant,
        status=Certificate.Status.REVOKED,
        user=None,
        reason="Initial revoke",
        timestamp=timezone.now(),
    )

    # Attempt to revoke a second time to mimic an accidental double action.
    update_certificate_status(
        consultant,
        status=Certificate.Status.REVOKED,
        user=None,
        reason="Second revoke",
        timestamp=timezone.now() + timedelta(seconds=5),
    )

    certificate.refresh_from_db()
    assert certificate.status == Certificate.Status.REVOKED
    assert certificate.status_reason == "Second revoke"

    with pytest.raises(CertificateTokenError) as exc:
        verify_certificate_token(token, consultant)

    assert str(exc.value) == "Certificate has been revoked."


@pytest.mark.django_db
def test_certificate_token_invalid_for_other_consultant(consultant_with_certificate):
    other_user = get_user_model().objects.create_user(
        username="other", email="other@example.com", password="pass1234"
    )
    other_consultant = Consultant.objects.create(
        user=other_user,
        full_name="Other Consultant",
        id_number="ID-999",
        dob=timezone.now().date(),
        gender="M",
        nationality="Kenya",
        email="other@example.com",
        phone_number="0700000001",
        business_name="Other Business",
        status="approved",
        submitted_at=timezone.now(),
    )

    token = build_certificate_token(consultant_with_certificate)

    with pytest.raises(CertificateTokenError):
        verify_certificate_token(token, other_consultant)


@pytest.mark.django_db
def test_build_verification_url_includes_uuid(consultant_with_certificate):
    consultant = consultant_with_certificate

    url = build_verification_url(consultant)

    assert str(consultant.certificate_uuid) in url


@pytest.mark.django_db
def test_verify_certificate_view_success(client, consultant_with_certificate):
    consultant = consultant_with_certificate
    token = build_certificate_token(consultant)

    url = reverse(
        "consultant-certificate-verify",
        kwargs={"certificate_uuid": consultant.certificate_uuid},
    )
    response = client.get(url, {"token": token})

    assert response.status_code == 200
    assert response.context["verified"] is True
    assert response.context["consultant"] == consultant
    assert response.context["certificate_id"] == str(consultant.certificate_uuid)
    assert response.context["certificate_status"] == "VALID"
    assert response.context["certificate_status_message"] == "Certificate verified successfully."
    assert response.context["certificate_status_display"] == "Valid"
    assert response.context["certificate_status_effective_at"] == consultant.certificate_generated_at
    assert response.context["certificate_status_reason"] is None
    assert response.context["issued_on"] == consultant.certificate_generated_at.date()
    assert response.context["expires_on"] == consultant.certificate_expires_at


@pytest.mark.django_db
def test_verify_certificate_view_marks_expired_certificate(client, consultant_with_certificate):
    consultant = consultant_with_certificate
    consultant.certificate_expires_at = timezone.localdate() - timedelta(days=1)
    consultant.save(update_fields=["certificate_expires_at"])
    token = build_certificate_token(consultant)
    certificate = Certificate.objects.latest_for_consultant(consultant)
    certificate.mark_status(
        Certificate.Status.EXPIRED,
        timestamp=timezone.now(),
        reason="Expired automatically",
    )

    url = reverse(
        "consultant-certificate-verify",
        kwargs={"certificate_uuid": consultant.certificate_uuid},
    )
    response = client.get(url, {"token": token})

    assert response.status_code == 410
    assert response.context["verified"] is False
    assert response.context["certificate_status"] == "EXPIRED"
    assert response.context["certificate_status_message"] == "This certificate has expired and can no longer be verified."
    assert response.context["certificate_status_reason"] == "Expired automatically"
    assert response.context["verification_error"] == "Certificate has expired."
    assert response.context["expires_on"] == consultant.certificate_expires_at


@pytest.mark.django_db
def test_verify_certificate_view_marks_revoked_certificate(client, consultant_with_certificate):
    consultant = consultant_with_certificate
    consultant.certificate_expires_at = timezone.localdate() + timedelta(days=10)
    consultant.save(update_fields=["certificate_expires_at"])
    token = build_certificate_token(consultant)
    certificate = Certificate.objects.latest_for_consultant(consultant)
    certificate.mark_status(
        Certificate.Status.REVOKED,
        timestamp=timezone.now(),
        reason="Revoked for testing",
    )

    url = reverse(
        "consultant-certificate-verify",
        kwargs={"certificate_uuid": consultant.certificate_uuid},
    )
    response = client.get(url, {"token": token})

    assert response.status_code == 410
    assert response.context["verified"] is False
    assert response.context["certificate_status"] == "REVOKED"
    assert response.context["certificate_status_message"] == "This certificate has been revoked and is no longer valid."
    assert response.context["certificate_status_reason"] == "Revoked for testing"
    assert response.context["verification_error"] == "Certificate has been revoked."


@pytest.mark.django_db
def test_verify_certificate_view_handles_reissued_certificate(client, consultant_with_certificate):
    consultant = consultant_with_certificate
    token = build_certificate_token(consultant)
    certificate = Certificate.objects.latest_for_consultant(consultant)
    certificate.mark_status(
        Certificate.Status.REISSUED,
        timestamp=timezone.now(),
        reason="Reissued with updated details",
    )

    url = reverse(
        "consultant-certificate-verify",
        kwargs={"certificate_uuid": consultant.certificate_uuid},
    )
    response = client.get(url, {"token": token})

    assert response.status_code == 409
    assert response.context["verified"] is False
    assert response.context["certificate_status"] == "REISSUED"
    assert response.context["certificate_status_message"] == "This certificate has been replaced by a new issue."
    assert response.context["certificate_status_reason"] == "Reissued with updated details"
    assert response.context["verification_error"] == "Token is no longer valid for this certificate."


@pytest.mark.django_db
def test_verify_certificate_view_rejects_invalid_token(client, consultant_with_certificate):
    consultant = consultant_with_certificate
    url = reverse(
        "consultant-certificate-verify",
        kwargs={"certificate_uuid": consultant.certificate_uuid},
    )
    response = client.get(url, {"token": "invalid-token"})

    assert response.status_code == 400
    assert response.context["verified"] is False
    assert response.context["verification_error"] == "Invalid Certificate"
    assert response.context["certificate_status_message"] == "Invalid Certificate"


@pytest.mark.django_db
def test_verify_certificate_view_handles_missing_certificate(client, consultant_with_certificate):
    consultant = consultant_with_certificate
    consultant.certificate_pdf.delete(save=True)
    consultant.refresh_from_db()

    url = reverse(
        "consultant-certificate-verify",
        kwargs={"certificate_uuid": consultant.certificate_uuid},
    )
    response = client.get(url, {"token": "anything"})

    assert response.status_code == 404
    assert response.context["verified"] is False


@pytest.mark.django_db
def test_verify_certificate_view_uses_uuid_lookup(client, consultant_with_certificate):
    _ = consultant_with_certificate  # ensure fixture creates consultant
    random_uuid = uuid.uuid4()

    url = reverse(
        "consultant-certificate-verify",
        kwargs={"certificate_uuid": random_uuid},
    )
    response = client.get(url)

    assert response.status_code == 404
