from __future__ import annotations

from importlib import reload
from io import StringIO

import pytest
from django.core.management import call_command

from apps.users.constants import UserRole
from tests.utils import create_consultant_instance


@pytest.fixture()
def celery_tasks(settings):
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = False

    import consultant_app.tasks as tasks_module

    reload(tasks_module)
    tasks_module.celery_app.conf.task_always_eager = True
    tasks_module.celery_app.conf.task_eager_propagates = False
    return tasks_module


@pytest.mark.django_db
def test_send_confirmation_email_executes_eagerly(celery_tasks, user_factory, mocker):
    user = user_factory(username="celery-success", role=UserRole.CONSULTANT)
    consultant = create_consultant_instance(user, email="celery-success@example.com")

    mocked_email = mocker.patch(
        "apps.consultants.emails.send_submission_confirmation_email"
    )

    result = celery_tasks.send_confirmation_email.delay(consultant.email)

    assert result.get() is None
    mocked_email.assert_called_once_with(consultant)


@pytest.mark.django_db
def test_send_confirmation_email_retries_and_logs(celery_tasks, user_factory, mocker, caplog):
    user = user_factory(username="celery-retry", role=UserRole.CONSULTANT)
    consultant = create_consultant_instance(user, email="celery-retry@example.com")

    mocked_email = mocker.patch(
        "apps.consultants.emails.send_submission_confirmation_email",
        side_effect=[ConnectionError("temporary"), None],
    )

    caplog.set_level("INFO", logger="consultant_app.tasks")

    result = celery_tasks.send_confirmation_email.delay(consultant.pk)

    assert result.get() is None
    assert mocked_email.call_count == 2
    assert any(
        "Failed to send confirmation email" in record.getMessage()
        for record in caplog.records
    )
    assert any(
        "Sent confirmation email" in record.getMessage()
        for record in caplog.records
    )


@pytest.mark.django_db
def test_management_command_enqueues_task(celery_tasks, user_factory, mocker):
    user = user_factory(username="celery-command", role=UserRole.CONSULTANT)
    consultant = create_consultant_instance(user, email="celery-command@example.com")

    fake_result = mocker.Mock()
    fake_result.id = "task-123"

    mocked_delay = mocker.patch(
        "consultant_app.tasks.send_confirmation_email.delay",
        return_value=fake_result,
    )

    stdout = StringIO()
    call_command("send_test_confirmation_email", consultant.email, stdout=stdout)

    mocked_delay.assert_called_once_with(consultant.email)
    assert "task-123" in stdout.getvalue()
