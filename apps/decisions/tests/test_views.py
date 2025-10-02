import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse

from apps.consultants.models import Consultant
from apps.users.constants import BOARD_COMMITTEE_GROUP_NAME


@pytest.fixture
@pytest.mark.django_db
def reviewer_user(db):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="board_member",
        email="board@example.com",
        password="password123",
        first_name="Board",
        last_name="Member",
    )
    group, _ = Group.objects.get_or_create(name=BOARD_COMMITTEE_GROUP_NAME)
    user.groups.add(group)
    return user


@pytest.fixture
@pytest.mark.django_db
def consultant(db, reviewer_user):
    applicant_model = get_user_model()
    applicant = applicant_model.objects.create_user(
        username="applicant_view",
        email="applicant_view@example.com",
        password="password123",
    )
    return Consultant.objects.create(
        user=applicant,
        full_name="Applicant View",
        id_number="ID999",
        dob="1990-01-01",
        gender="M",
        nationality="Country",
        email=applicant.email,
        phone_number="555-0100",
        business_name="BizView",
        status="vetted",
    )


@pytest.mark.django_db
def test_decisions_dashboard_uses_service(client, mocker, reviewer_user, consultant):
    service = mocker.patch("apps.decisions.views.process_decision_action")
    client.force_login(reviewer_user)

    response = client.post(
        reverse("decisions_dashboard"),
        {
            "consultant_id": str(consultant.pk),
            "action": "approved",
            "notes": "Looks good",
        },
        follow=False,
    )

    assert response.status_code == 302
    service.assert_called_once()
    called_consultant, called_action, called_user = service.call_args[0]
    assert called_consultant == consultant
    assert called_action == "approved"
    assert called_user == reviewer_user
    assert service.call_args.kwargs.get("notes") == "Looks good"


@pytest.mark.django_db
def test_application_detail_uses_service(client, mocker, reviewer_user, consultant):
    service = mocker.patch("apps.decisions.views.process_decision_action")
    client.force_login(reviewer_user)

    response = client.post(
        reverse("officer_application_detail", args=[consultant.pk]),
        {
            "action": "rejected",
            "notes": "Needs more documents",
        },
    )

    assert response.status_code == 302
    service.assert_called_once()
    called_consultant, called_action, called_user = service.call_args[0]
    assert called_consultant == consultant
    assert called_action == "rejected"
    assert called_user == reviewer_user
    assert service.call_args.kwargs.get("notes") == "Needs more documents"
