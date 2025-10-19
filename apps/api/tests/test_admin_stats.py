import pytest
from datetime import date, datetime, timezone as dt_timezone

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.api.serializers import AdminStatsSerializer
from apps.users.constants import UserRole as Roles
from apps.consultants.models import Consultant as Application
from consultant_app.models import Certificate


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


def _create_application(user, **overrides):
    defaults = {
        "full_name": "Example Applicant",
        "id_number": f"ID-{user.username}",
        "dob": date(1990, 1, 1),
        "gender": "F",
        "nationality": "Testland",
        "email": f"{user.username}@example.com",
        "phone_number": "0712345678",
        "business_name": "Example Business",
        "consultant_type": "General",
        "status": "submitted",
        "submitted_at": timezone.now(),
    }
    defaults.update(overrides)
    return Application.objects.create(user=user, **defaults)


@pytest.mark.django_db
def test_admin_stats_endpoint_returns_metrics(api_client, user_factory):
    admin = user_factory(username="stats-admin", role=Roles.ADMIN)
    api_client.force_authenticate(user=admin)

    applicant_one = get_user_model().objects.create_user(
        username="app-one", password="pass123", email="one@example.com"
    )
    applicant_two = get_user_model().objects.create_user(
        username="app-two", password="pass123", email="two@example.com"
    )
    applicant_three = get_user_model().objects.create_user(
        username="app-three", password="pass123", email="three@example.com"
    )
    draft_user = get_user_model().objects.create_user(
        username="app-draft", password="pass123", email="draft@example.com"
    )

    month_one = datetime(2024, 1, 15, tzinfo=dt_timezone.utc)
    month_two = datetime(2024, 2, 10, tzinfo=dt_timezone.utc)

    approved = _create_application(
        applicant_one,
        status="approved",
        submitted_at=month_one,
    )
    pending = _create_application(
        applicant_two,
        status="submitted",
        submitted_at=month_two,
    )
    _create_application(
        applicant_three,
        status="rejected",
        submitted_at=month_two,
    )
    _create_application(
        draft_user,
        status="draft",
        submitted_at=None,
    )

    Certificate.objects.create(consultant=approved, status=Certificate.Status.VALID)
    Certificate.objects.create(consultant=pending, status=Certificate.Status.REVOKED)

    url = reverse("api:admin-stats")
    response = api_client.get(url)

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()

    assert payload["total_applications"] == 3
    assert payload["status_breakdown"] == {
        "approved": 1,
        "pending": 1,
        "rejected": 1,
        "revoked": 1,
    }

    monthly = {entry["month"]: entry["total"] for entry in payload["monthly_trends"]}
    assert monthly["2024-01-01T00:00:00+00:00"] == 1
    assert monthly["2024-02-01T00:00:00+00:00"] == 2

    certificate_counts = {
        item["status"]: item["count"] for item in payload["certificate_statuses"]
    }
    assert certificate_counts[Certificate.Status.VALID] == 1
    assert certificate_counts[Certificate.Status.REVOKED] == 1


@pytest.mark.django_db
def test_admin_stats_requires_staff_permissions(api_client):
    user = get_user_model().objects.create_user(
        username="no-staff", password="pass123", email="no-staff@example.com"
    )
    api_client.force_authenticate(user=user)

    response = api_client.get(reverse("api:admin-stats"))

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_admin_stats_serializer_validation():
    serializer = AdminStatsSerializer(
        data={
            "total_applications": 5,
            "status_breakdown": {
                "approved": 2,
                "pending": 1,
                "rejected": 1,
                "revoked": 1,
            },
            "monthly_trends": [
                {"month": "2024-01-01", "total": 2},
                {"month": "2024-02-01", "total": 3},
            ],
            "certificate_statuses": [
                {"status": "valid", "label": "Valid", "count": 2},
                {"status": "revoked", "label": "Revoked", "count": 1},
            ],
        }
    )

    assert serializer.is_valid(), serializer.errors
