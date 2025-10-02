"""Tests for the decision notification email helper."""

from datetime import date

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.consultants.models import Consultant
from apps.decisions.emails import send_decision_email


@pytest.fixture
def consultant_factory(db):
    """Return a factory that builds consultants with sample documents."""

    def _create(suffix: str) -> Consultant:
        user_model = get_user_model()
        user = user_model.objects.create_user(
            username=f"consultant_{suffix}",
            email=f"consultant_{suffix}@example.com",
            password="password123",
        )

        return Consultant.objects.create(
            user=user,
            full_name=f"Consultant {suffix.title()}",
            id_number="ID123456",
            dob=date(1990, 1, 1),
            gender="M",
            nationality="Examplestan",
            email=user.email,
            phone_number="555-0000",
            business_name="Example Consulting",
            registration_number="REG-001",
            certificate_pdf=SimpleUploadedFile(
                "certificate.pdf",
                b"certificate-bytes",
                content_type="application/pdf",
            ),
            rejection_letter=SimpleUploadedFile(
                "rejection.pdf",
                b"rejection-bytes",
                content_type="application/pdf",
            ),
        )

    return _create


@pytest.mark.django_db
def test_send_decision_email_for_approved_action_is_case_insensitive(mailoutbox, consultant_factory):
    consultant = consultant_factory("approved")

    delivery_count = send_decision_email(consultant, "ApProVed")

    assert delivery_count == 1
    assert len(mailoutbox) == 1

    message = mailoutbox[0]
    assert message.subject == "Your consultant application has been approved"
    assert message.body.startswith(f"Hello {consultant.full_name},")
    assert "approval certificate" in message.body
    assert message.to == [consultant.email]

    assert len(message.attachments) == 1
    filename, content, mimetype = message.attachments[0]
    assert filename.startswith("certificate")
    assert filename.endswith(".pdf")
    assert mimetype == "application/pdf"
    assert content == b"certificate-bytes"


@pytest.mark.django_db
def test_send_decision_email_for_rejected_action_includes_rejection_letter(mailoutbox, consultant_factory):
    consultant = consultant_factory("rejected")

    delivery_count = send_decision_email(consultant, "rejected")

    assert delivery_count == 1
    assert len(mailoutbox) == 1

    message = mailoutbox[0]
    assert message.subject == "Update on your consultant application"
    assert message.body.startswith(f"Hello {consultant.full_name},")
    assert "declined" in message.body
    assert message.to == [consultant.email]

    assert len(message.attachments) == 1
    filename, content, mimetype = message.attachments[0]
    assert filename.startswith("rejection")
    assert filename.endswith(".pdf")
    assert mimetype == "application/pdf"
    assert content == b"rejection-bytes"


@pytest.mark.django_db
def test_send_decision_email_ignores_unsupported_action(mailoutbox, consultant_factory):
    consultant = consultant_factory("ignored")

    delivery_count = send_decision_email(consultant, "vetted")

    assert delivery_count is None
    assert len(mailoutbox) == 0
