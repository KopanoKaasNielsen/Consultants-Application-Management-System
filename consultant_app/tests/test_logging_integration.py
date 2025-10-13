from datetime import date

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse

from apps.consultants.models import Consultant, LogEntry
from apps.users.constants import CONSULTANTS_GROUP_NAME


@pytest.fixture
def consultant_group(db):
    return Group.objects.get_or_create(name=CONSULTANTS_GROUP_NAME)[0]


@pytest.fixture
def staff_group(db):
    return Group.objects.get_or_create(name="Staff")[0]


@pytest.fixture
def consultant_user(consultant_group):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="consultant_user",
        email="consultant@example.com",
        password="password123",
    )
    user.groups.add(consultant_group)
    return user


@pytest.fixture
def staff_user(staff_group):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="staff_user",
        email="staff@example.com",
        password="password123",
    )
    user.groups.add(staff_group)
    return user


@pytest.fixture(autouse=True)
def clear_log_entries():
    LogEntry.objects.all().delete()
    yield
    LogEntry.objects.all().delete()


@pytest.mark.django_db
def test_submit_application_creates_log_entry(client, consultant_user, monkeypatch):
    monkeypatch.setattr(
        "apps.consultants.views.send_submission_confirmation_email_task.delay",
        lambda consultant_id: None,
    )

    client.force_login(consultant_user)

    payload = {
        "full_name": "Log Tester",
        "id_number": "ID-123",
        "dob": "1990-01-01",
        "gender": "M",
        "nationality": "Kenya",
        "email": "consultant@example.com",
        "phone_number": "0700000000",
        "business_name": "Testing & Co.",
        "registration_number": "REG-001",
        "action": "draft",
    }

    response = client.post(reverse("submit_application"), payload, follow=False)

    assert response.status_code in {200, 302}
    entries = list(LogEntry.objects.order_by("timestamp"))
    assert entries, "Expected a log entry for saving the draft"
    latest_entry = entries[-1]
    assert latest_entry.level == "INFO"
    assert latest_entry.user_id == consultant_user.id
    assert latest_entry.context.get("action") == "save_draft"
    assert latest_entry.context.get("consultant_id") is not None


@pytest.mark.django_db
def test_staff_dashboard_status_change_logs_action(client, staff_user):
    consultant = Consultant.objects.create(
        user=staff_user,  # placeholder user owner for consultant record
        full_name="Applicant",
        id_number="A-1",
        dob=date(1990, 1, 1),
        gender="M",
        nationality="Kenya",
        email="applicant@example.com",
        phone_number="0700000000",
        business_name="Applicant Biz",
        registration_number="REG-200",
        status="submitted",
    )

    client.force_login(staff_user)

    response = client.post(
        reverse("staff_dashboard"),
        {
            "consultant_id": consultant.pk,
            "action": "approved",
            "comment": "Looks good",
        },
        follow=False,
    )

    assert response.status_code == 302
    actions = {entry.context.get("action") for entry in LogEntry.objects.all()}
    assert "staff_dashboard.approved" in actions
    assert "notification.dispatch" in actions
    for entry in LogEntry.objects.filter(context__action="staff_dashboard.approved"):
        assert entry.user_id == staff_user.id
        assert entry.context.get("consultant_id") == consultant.pk


@pytest.mark.django_db
def test_log_entry_api_requires_staff(client, consultant_user):
    client.force_login(consultant_user)
    response = client.get("/api/staff/logs/")
    assert response.status_code == 403


@pytest.mark.django_db
def test_log_entry_api_returns_filtered_entries(client, staff_user):
    other_user = get_user_model().objects.create_user(
        username="other", email="other@example.com", password="pass12345"
    )

    entry_one = LogEntry.objects.create(
        logger_name="apps.consultants.views",
        level="INFO",
        message="First entry",
        user=staff_user,
        context={"action": "test.action", "consultant_id": 1},
    )
    LogEntry.objects.create(
        logger_name="apps.users.views",
        level="ERROR",
        message="Second entry",
        user=other_user,
        context={"action": "other.action", "consultant_id": 2},
    )

    client.force_login(staff_user)

    response = client.get(
        "/api/staff/logs/",
        {"level": "INFO", "action": "test.action", "user_id": staff_user.id},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["pagination"]["total_results"] == 1
    result = payload["results"][0]
    assert result["id"] == entry_one.pk
    assert result["context"]["action"] == "test.action"
    assert result["user"]["id"] == staff_user.id
