"""Tests for consultant dashboard export endpoints."""

from __future__ import annotations

import csv
import io

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from consultant_app.models import Certificate


@pytest.fixture
def staff_user(db):
    user_model = get_user_model()
    return user_model.objects.create_user(
        username="staffadmin",
        email="staff@example.com",
        password="testpass123",
        is_superuser=True,
    )


@pytest.fixture
def consultant_factory(db):
    from apps.consultants.models import Consultant

    counter = 0

    def factory(**overrides):
        nonlocal counter
        counter += 1
        user_model = get_user_model()
        user = overrides.pop("user", None)
        if user is None:
            user = user_model.objects.create_user(
                username=f"consultant{counter}",
                email=f"consultant{counter}@example.com",
                password="testpass123",
            )

        defaults = {
            "user": user,
            "full_name": overrides.pop("full_name", f"Consultant {counter}"),
            "id_number": overrides.pop("id_number", f"ID-{counter}"),
            "dob": overrides.pop("dob", timezone.now().date()),
            "gender": overrides.pop("gender", "M"),
            "nationality": overrides.pop("nationality", "Kenya"),
            "email": overrides.pop("email", f"consultant{counter}@example.com"),
            "phone_number": overrides.pop("phone_number", "0700000000"),
            "business_name": overrides.pop("business_name", f"Business {counter}"),
            "registration_number": overrides.pop("registration_number", f"REG-{counter}"),
            "status": overrides.pop("status", "submitted"),
            "submitted_at": overrides.pop("submitted_at", timezone.now()),
            "consultant_type": overrides.pop("consultant_type", "General"),
        }

        defaults.update(overrides)
        return Consultant.objects.create(**defaults)

    return factory


@pytest.mark.django_db
def test_csv_export_respects_filters(client, staff_user, consultant_factory):
    approved = consultant_factory(
        full_name="Alice Export",
        status="approved",
        consultant_type="Legal",
    )
    consultant_factory(
        full_name="Bob Ignore",
        status="submitted",
        consultant_type="Financial",
    )

    Certificate.objects.create(
        consultant=approved,
        status=Certificate.Status.VALID,
        issued_at=timezone.now(),
    )

    client.force_login(staff_user)

    response = client.get(
        "/api/staff/consultants/export/csv/",
        {"status": "approved", "category": "legal"},
    )

    assert response.status_code == 200
    assert response["Content-Type"] == "text/csv"
    assert response["Content-Disposition"].endswith(".csv")

    reader = csv.DictReader(io.StringIO(response.content.decode("utf-8")))
    rows = list(reader)
    assert len(rows) == 1
    row = rows[0]
    assert row["Full name"] == "Alice Export"
    assert row["Status"] == "Approved"
    assert row["Consultant type"] == "Legal"
    assert row["Certificate status"] == "Valid"


@pytest.mark.django_db
def test_pdf_export_returns_pdf_document(client, staff_user, consultant_factory):
    consultant_factory(
        full_name="Zara Pdf",
        status="approved",
        consultant_type="Financial",
    )

    client.force_login(staff_user)

    response = client.get(
        "/api/staff/consultants/export/pdf/",
        {"status": "approved"},
    )

    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert response["Content-Disposition"].endswith(".pdf")
    assert response.content.startswith(b"%PDF")


@pytest.mark.django_db
def test_exports_require_staff_permissions(client, consultant_factory):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="regular", email="regular@example.com", password="testpass123"
    )
    consultant_factory()
    client.force_login(user)

    response = client.get("/api/staff/consultants/export/csv/")
    assert response.status_code == 403
