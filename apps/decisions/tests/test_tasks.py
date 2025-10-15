import pytest

from django.contrib.auth import get_user_model

from apps.consultants.models import Consultant

from apps.decisions.tasks import (
    generate_approval_certificate_task,
    generate_rejection_letter_task,
)


@pytest.fixture
@pytest.mark.django_db
def consultant(db):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="task-applicant",
        email="task-applicant@example.com",
        password="password123",
    )
    return Consultant.objects.create(
        user=user,
        full_name="Task Applicant",
        id_number="ID999",
        dob="1990-01-01",
        gender="F",
        nationality="Country",
        email=user.email,
        phone_number="555-1111",
        business_name="Task Biz",
    )


@pytest.mark.django_db
def test_generate_approval_certificate_task_dispatches_email_after_document(
    mocker, consultant
):
    send_email = mocker.patch("apps.decisions.tasks.send_decision_email_task.delay")

    def ensure_email_not_yet_called(*args, **kwargs):
        assert not send_email.called

    generate = mocker.patch(
        "apps.decisions.tasks.generate_approval_certificate",
        side_effect=ensure_email_not_yet_called,
    )

    generate_approval_certificate_task(consultant.pk, generated_by="Reviewer")

    generate.assert_called_once_with(
        consultant, generated_by="Reviewer", actor=None
    )
    send_email.assert_called_once_with(consultant.pk, "approved")


@pytest.mark.django_db
def test_generate_rejection_letter_task_dispatches_email_after_document(
    mocker, consultant
):
    send_email = mocker.patch("apps.decisions.tasks.send_decision_email_task.delay")

    def ensure_email_not_yet_called(*args, **kwargs):
        assert not send_email.called

    generate = mocker.patch(
        "apps.decisions.tasks.generate_rejection_letter",
        side_effect=ensure_email_not_yet_called,
    )

    generate_rejection_letter_task(consultant.pk, generated_by="Reviewer")

    generate.assert_called_once_with(
        consultant, generated_by="Reviewer", actor=None
    )
    send_email.assert_called_once_with(consultant.pk, "rejected")


@pytest.fixture
@pytest.mark.django_db
def decision_actor(db):
    user_model = get_user_model()
    return user_model.objects.create_user(
        username="task-reviewer",
        email="task-reviewer@example.com",
        password="password123",
        first_name="Task",
        last_name="Reviewer",
    )


@pytest.mark.django_db
def test_generate_approval_certificate_task_passes_actor(
    mocker, consultant, decision_actor
):
    send_email = mocker.patch("apps.decisions.tasks.send_decision_email_task.delay")
    generate = mocker.patch("apps.decisions.tasks.generate_approval_certificate")

    generate_approval_certificate_task(
        consultant.pk,
        generated_by="Reviewer",
        actor_id=decision_actor.pk,
    )

    generate.assert_called_once_with(
        consultant, generated_by="Reviewer", actor=decision_actor
    )
    send_email.assert_called_once_with(consultant.pk, "approved")
