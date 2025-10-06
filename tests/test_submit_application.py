import pytest
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.users.constants import UserRole as Roles
from apps.consultants.models import Consultant

@pytest.mark.django_db
def test_submit_application_success(client, user_factory, mocker):
    # Setup user with CONSULTANT role
    user = user_factory(role=Roles.CONSULTANT)
    client.force_login(user)

    # Mock the email send function
    mock_send = mocker.patch(
        "apps.consultants.views.send_submission_confirmation_email"
    )

    # Build form data
    data = {
        "action": "submit",
        "cv": SimpleUploadedFile("cv.pdf", b"file content", content_type="application/pdf"),
        "experience": "5 years consulting experience",
        "reference_letter": SimpleUploadedFile("ref.pdf", b"file content", content_type="application/pdf"),
        "passport_photo": SimpleUploadedFile("photo.jpg", b"fakeimage", content_type="image/jpeg"),
    }

    # Post to submit_application view
    url = reverse("submit_application")
    response = client.post(url, data, follow=True)

    # Assertions
    assert response.status_code == 200
    consultant = Consultant.objects.get(user=user)
    assert consultant.status == "submitted"
    assert consultant.submitted_at is not None
    mock_send.assert_called_once_with(consultant)
