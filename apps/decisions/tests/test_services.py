import pytest
from django.contrib.auth import get_user_model

from apps.consultants.models import Consultant
from apps.decisions.models import ApplicationAction
from apps.decisions.services import process_decision_action


@pytest.fixture
@pytest.mark.django_db
def consultant(db):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="applicant",
        email="applicant@example.com",
        password="password123",
    )
    return Consultant.objects.create(
        user=user,
        full_name="Applicant One",
        id_number="ID123",
        dob="1990-01-01",
        gender="M",
        nationality="Country",
        email=user.email,
        phone_number="555-0000",
        business_name="Biz",
    )


@pytest.fixture
@pytest.mark.django_db
def actor(db):
    user_model = get_user_model()
    return user_model.objects.create_user(
        username="reviewer",
        email="reviewer@example.com",
        password="password123",
        first_name="Review",
        last_name="Er",
    )


@pytest.mark.django_db
def test_process_decision_action_queues_approval_tasks(mocker, consultant, actor):
    generate_task = mocker.patch(
        "apps.decisions.services.generate_approval_certificate_task.delay"
    )
    email_task = mocker.patch("apps.decisions.tasks.send_decision_email_task.delay")

    action = process_decision_action(consultant, "approved", actor, notes="All good")

    consultant.refresh_from_db()

    assert consultant.status == "approved"
    assert ApplicationAction.objects.filter(pk=action.pk, action="approved").exists()
    generate_task.assert_called_once_with(consultant.pk, "Review Er")
    email_task.assert_not_called()


@pytest.mark.django_db
def test_process_decision_action_queues_rejection_tasks(mocker, consultant, actor):
    generate_task = mocker.patch(
        "apps.decisions.services.generate_rejection_letter_task.delay"
    )
    email_task = mocker.patch("apps.decisions.tasks.send_decision_email_task.delay")

    process_decision_action(consultant, "rejected", actor)

    consultant.refresh_from_db()

    assert consultant.status == "rejected"
    generate_task.assert_called_once_with(consultant.pk, "Review Er")
    email_task.assert_not_called()


@pytest.mark.django_db
def test_process_decision_action_for_vetted_has_no_tasks(mocker, consultant, actor):
    send_email = mocker.patch("apps.decisions.tasks.send_decision_email_task.delay")
    approval_task = mocker.patch(
        "apps.decisions.services.generate_approval_certificate_task.delay"
    )
    rejection_task = mocker.patch(
        "apps.decisions.services.generate_rejection_letter_task.delay"
    )

    process_decision_action(consultant, "vetted", actor)

    consultant.refresh_from_db()
    assert consultant.status == "vetted"
    send_email.assert_not_called()
    approval_task.assert_not_called()
    rejection_task.assert_not_called()
    assert ApplicationAction.objects.filter(action="vetted").exists()
