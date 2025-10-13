import pytest
from django.contrib.messages import get_messages
from django.urls import reverse
from django.utils import timezone

from apps.users.constants import UserRole as Roles
from apps.consultants.models import Consultant

from tests.utils import (
    consultant_form_data,
    consultant_form_files,
    create_consultant_instance,
)


@pytest.mark.django_db
def test_submit_application_success(client, user_factory, mocker):
    user = user_factory(role=Roles.CONSULTANT)
    client.force_login(user)

    mock_delay = mocker.patch(
        "apps.consultants.views.send_submission_confirmation_email_task.delay"
    )

    payload = {**consultant_form_data(), **consultant_form_files()}

    url = reverse("submit_application")
    response = client.post(url, payload)

    assert response.status_code == 302
    assert response["Location"].endswith(reverse("dashboard"))
    consultant = Consultant.objects.get(user=user)
    assert consultant.status == "submitted"
    assert consultant.submitted_at is not None
    mock_delay.assert_called_once_with(consultant.pk)


@pytest.mark.django_db
def test_submit_application_redirects_when_already_submitted(client, user_factory):
    user = user_factory(role=Roles.CONSULTANT)
    create_consultant_instance(
        user,
        status="submitted",
        submitted_at=timezone.now(),
    )
    client.force_login(user)

    url = reverse("submit_application")
    response = client.get(url)

    assert response.status_code == 302
    assert response["Location"].endswith(reverse("dashboard"))

    messages = list(get_messages(response.wsgi_request))
    assert any(
        message.message == "You have already submitted your application."
        and message.level_tag == "info"
        for message in messages
    )
    assert Consultant.objects.filter(user=user).count() == 1


@pytest.mark.django_db
def test_submit_application_handles_email_failure(client, user_factory, mocker):
    user = user_factory(role=Roles.CONSULTANT)
    client.force_login(user)

    mock_delay = mocker.patch(
        "apps.consultants.views.send_submission_confirmation_email_task.delay",
        side_effect=Exception("email failure"),
    )

    payload = {**consultant_form_data(), **consultant_form_files()}

    url = reverse("submit_application")
    response = client.post(url, payload)

    consultant = Consultant.objects.get(user=user)
    assert consultant.status == "submitted"
    assert consultant.submitted_at is not None
    mock_delay.assert_called_once_with(consultant.pk)

    messages = list(get_messages(response.wsgi_request))
    assert any(
        "confirmation email failed" in message.message
        and message.level_tag == "warning"
        for message in messages
    )
