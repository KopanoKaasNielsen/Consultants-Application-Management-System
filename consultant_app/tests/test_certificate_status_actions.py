"""Tests covering shared helpers for certificate status transitions."""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.consultants.models import Consultant
from consultant_app.certificates import update_certificate_status
from consultant_app.models import Certificate, LogEntry


@pytest.fixture
def staff_user(db):
    user_model = get_user_model()
    return user_model.objects.create_user(
        username="certificate-staff",
        email="staff-cert@example.com",
        password="safe-pass-123",
    )


@pytest.fixture
def consultant_with_active_certificate(db):
    user_model = get_user_model()
    applicant = user_model.objects.create_user(
        username="certificate-applicant",
        email="applicant-cert@example.com",
        password="safe-pass-456",
    )

    consultant = Consultant.objects.create(
        user=applicant,
        full_name="Cert Test",
        id_number="CERT-001",
        dob=timezone.now().date(),
        gender="M",
        nationality="Kenya",
        email="applicant-cert@example.com",
        phone_number="0700000000",
        business_name="Certificate Testing",
        registration_number="REG-001",
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
def test_update_certificate_status_records_reason_and_logs(
    staff_user, consultant_with_active_certificate
):
    LogEntry.objects.all().delete()
    consultant, certificate = consultant_with_active_certificate

    reason = "Revoked for compliance review"
    update_certificate_status(
        consultant,
        status=Certificate.Status.REVOKED,
        user=staff_user,
        reason=reason,
        context={"source": "unit-test"},
    )

    certificate.refresh_from_db()
    assert certificate.status == Certificate.Status.REVOKED
    assert certificate.status_reason == reason
    assert certificate.revoked_at is not None

    log_entry = LogEntry.objects.latest("timestamp")
    assert log_entry.user_id == staff_user.pk
    assert log_entry.context["action"] == "certificate.status.revoked"
    assert log_entry.context["consultant_id"] == consultant.pk
    assert log_entry.context["reason"] == reason
    assert log_entry.context["source"] == "unit-test"


@pytest.mark.django_db
def test_update_certificate_status_logs_missing_certificate(staff_user):
    LogEntry.objects.all().delete()
    user_model = get_user_model()
    applicant = user_model.objects.create_user(
        username="missing-cert",
        email="missing-cert@example.com",
        password="safe-pass-789",
    )

    consultant = Consultant.objects.create(
        user=applicant,
        full_name="No Certificate",
        id_number="CERT-404",
        dob=timezone.now().date(),
        gender="F",
        nationality="Kenya",
        email="missing-cert@example.com",
        phone_number="0700000001",
        business_name="Missing Certificate Ltd",
        registration_number="REG-404",
        status="approved",
        submitted_at=timezone.now(),
    )

    result = update_certificate_status(
        consultant,
        status=Certificate.Status.REVOKED,
        user=staff_user,
        reason="Unable to locate certificate",
    )

    assert result is None
    log_entry = LogEntry.objects.latest("timestamp")
    assert log_entry.context["action"] == "certificate.status.missing"
    assert log_entry.context["consultant_id"] == consultant.pk
    assert log_entry.context["requested_status"] == Certificate.Status.REVOKED.value
