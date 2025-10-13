from __future__ import annotations

import uuid
from io import BytesIO

import pytest
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from apps.consultants.models import Consultant
from consultant_app.certificates import (
    CertificateTokenError,
    build_certificate_token,
    build_verification_url,
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
    assert "Invalid" in response.context["verification_error"]


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
