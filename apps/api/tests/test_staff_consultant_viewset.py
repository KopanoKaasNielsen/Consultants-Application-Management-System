import pytest

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.consultants.models import Consultant as Application
from apps.users.constants import UserRole as Roles
from consultant_app.models import Certificate


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


def _create_application(user, **overrides):
    defaults = {
        "full_name": "Example Applicant",
        "id_number": f"ID-{user.username}",
        "dob": timezone.now().date(),
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
def test_staff_consultant_list_prefetches_certificates(
    api_client, user_factory, django_assert_num_queries
):
    staff_user = user_factory(username="staff-admin", role=Roles.STAFF)
    api_client.force_authenticate(user=staff_user)

    applicant_model = get_user_model()
    for index in range(3):
        applicant = applicant_model.objects.create_user(
            username=f"applicant-{index}",
            password="pass123",
            email=f"applicant-{index}@example.com",
        )
        application = _create_application(
            applicant,
            full_name=f"Applicant {index}",
            submitted_at=timezone.now(),
        )
        Certificate.objects.create(
            consultant=application,
            status=Certificate.Status.VALID,
        )

    url = reverse("api:staff-consultants-list")

    with django_assert_num_queries(5):
        response = api_client.get(url)

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["pagination"]["total_results"] == 3
    assert len(payload["results"]) == 3
