"""Tests for the consultant dashboard API endpoint."""

from __future__ import annotations

from datetime import date, timedelta
import itertools

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.consultants.models import Consultant


@pytest.fixture
def consultant_factory(db):
    """Create consultants with sensible defaults for dashboard tests."""

    user_model = get_user_model()
    counter = itertools.count()

    def factory(**overrides) -> Consultant:
        index = next(counter)
        user = overrides.pop("user", None)
        if user is None:
            user = user_model.objects.create_user(
                username=f"consultant{index}",
                email=f"consultant{index}@example.com",
                password="testpass123",
            )

        now = timezone.now()

        defaults = {
            "user": user,
            "full_name": overrides.pop("full_name", f"Consultant {index}"),
            "id_number": overrides.pop("id_number", f"ID-{index}"),
            "dob": overrides.pop("dob", date(1990, 1, 1)),
            "gender": overrides.pop("gender", "M"),
            "nationality": overrides.pop("nationality", "Kenya"),
            "email": overrides.pop("email", f"consultant{index}@example.com"),
            "phone_number": overrides.pop("phone_number", "0700000000"),
            "business_name": overrides.pop("business_name", f"Business {index}"),
            "registration_number": overrides.pop("registration_number", f"REG-{index}"),
            "status": overrides.pop("status", "submitted"),
            "submitted_at": overrides.pop("submitted_at", now),
        }

        defaults.update(overrides)
        return Consultant.objects.create(**defaults)

    return factory


@pytest.mark.django_db
def test_dashboard_returns_expected_fields(client, consultant_factory):
    consultant = consultant_factory(
        full_name="Alice Johnson",
        email="alice@example.com",
        status="approved",
        submitted_at=timezone.now(),
        photo="documents/photos/alice.jpg",
        id_document="documents/id/alice.pdf",
        cv="documents/cv/alice.pdf",
        police_clearance="documents/police/alice.pdf",
        qualifications="documents/qualifications/alice.pdf",
        business_certificate="documents/certificates/alice.pdf",
        certificate_expires_at=date.today() + timedelta(days=90),
    )

    response = client.get("/api/staff/consultants/")

    assert response.status_code == 200
    payload = response.json()
    assert payload["pagination"]["total_results"] == 1

    result = payload["results"][0]
    assert result["id"] == consultant.id
    assert result["name"] == "Alice Johnson"
    assert result["email"] == "alice@example.com"
    assert result["status"] == "approved"
    assert result["status_display"] == "Approved"
    assert result["documents"]["is_complete"] is True
    assert result["documents"]["missing"] == []
    assert result["certificate_expires_at"] is not None


@pytest.mark.django_db
def test_dashboard_filters_by_status_date_and_search(client, consultant_factory):
    now = timezone.now()
    consultant_factory(
        full_name="Old Approval",
        email="old@example.com",
        status="approved",
        submitted_at=now - timedelta(days=40),
    )
    consultant_factory(
        full_name="Submitted Draft",
        email="draft@example.com",
        status="submitted",
        submitted_at=now,
    )
    target = consultant_factory(
        full_name="Target Consultant",
        email="target@example.com",
        status="approved",
        submitted_at=now - timedelta(days=2),
    )

    response = client.get(
        "/api/staff/consultants/",
        {
            "status": "approved",
            "date_from": (now - timedelta(days=5)).date().isoformat(),
            "date_to": (now - timedelta(days=1)).date().isoformat(),
            "search": "target@example.com",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["pagination"]["total_results"] == 1
    assert payload["results"][0]["id"] == target.id


@pytest.mark.django_db
def test_dashboard_filters_by_category(client, consultant_factory):
    consultant_factory(
        full_name="Legal Specialist",
        consultant_type="Legal",
        status="approved",
    )
    consultant_factory(
        full_name="Finance Expert",
        consultant_type="Financial",
        status="approved",
    )

    response = client.get(
        "/api/staff/consultants/",
        {"category": "legal"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["pagination"]["total_results"] == 1
    assert payload["results"][0]["name"] == "Legal Specialist"
    assert payload["applied_filters"]["category"] == "legal"


@pytest.mark.django_db
def test_dashboard_supports_sorting_and_pagination(client, consultant_factory):
    consultant_factory(full_name="Charlie Example", submitted_at=timezone.now())
    consultant_factory(full_name="Alice Example", submitted_at=timezone.now())
    consultant_factory(full_name="Bob Example", submitted_at=timezone.now())

    response = client.get(
        "/api/staff/consultants/",
        {"sort": "name", "page_size": 2},
    )

    assert response.status_code == 200
    payload = response.json()
    assert [item["name"] for item in payload["results"]] == [
        "Alice Example",
        "Bob Example",
    ]
    assert payload["pagination"]["has_next"] is True
    assert payload["applied_filters"]["sort"] == "name"

    second_page = client.get(
        "/api/staff/consultants/",
        {"sort": "name", "page_size": 2, "page": 2},
    )
    second_payload = second_page.json()
    assert [item["name"] for item in second_payload["results"]] == ["Charlie Example"]
    assert second_payload["pagination"]["has_previous"] is True


@pytest.mark.django_db
def test_dashboard_reports_missing_documents(client, consultant_factory):
    consultant_factory(full_name="Docs Missing", submitted_at=timezone.now())

    response = client.get("/api/staff/consultants/")
    assert response.status_code == 200
    payload = response.json()
    documents = payload["results"][0]["documents"]
    assert documents["is_complete"] is False
    assert set(documents["missing"]) == {
        "Photo",
        "ID document",
        "CV",
        "Police clearance",
        "Qualifications",
        "Business certificate",
    }


@pytest.mark.django_db
def test_dashboard_excludes_draft_applications(client, consultant_factory):
    """Board reviewers should not see draft applications in the listing."""

    consultant_factory(status="draft", submitted_at=None)
    visible = consultant_factory(status="submitted", submitted_at=timezone.now())

    response = client.get("/api/staff/consultants/")

    assert response.status_code == 200
    payload = response.json()
    result_ids = [item["id"] for item in payload["results"]]
    assert result_ids == [visible.id]

    # Even when filtering explicitly for draft status, no records should be returned.
    filtered = client.get("/api/staff/consultants/", {"status": "draft"})
    assert filtered.status_code == 200
    assert filtered.json()["pagination"]["total_results"] == 0
