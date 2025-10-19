import os

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.consultants.models import Document
from apps.users.constants import UserRole as Roles

from tests.utils import create_consultant_instance


@pytest.fixture
@pytest.mark.django_db
def consultant_application(user_factory):
    user = user_factory(role=Roles.CONSULTANT)
    application = create_consultant_instance(user)
    return user, application


@pytest.mark.django_db
def test_consultant_can_upload_document(client, settings, tmp_path, consultant_application):
    settings.MEDIA_ROOT = tmp_path
    user, application = consultant_application
    client.force_login(user)

    upload = SimpleUploadedFile(
        "supporting.pdf", b"%PDF-1.4 test", content_type="application/pdf"
    )

    response = client.post(
        reverse("consultant_document_upload", args=[application.pk]),
        {"file": upload, "next": reverse("dashboard")},
    )

    assert response.status_code == 302
    document = Document.objects.get(application=application)
    assert document.original_name == "supporting.pdf"
    assert document.uploaded_by == user
    assert document.file.name.startswith(f"docs/{application.pk}/")
    assert os.path.exists(document.file.path)


@pytest.mark.django_db
def test_invalid_extension_rejected(client, settings, tmp_path, consultant_application):
    settings.MEDIA_ROOT = tmp_path
    user, application = consultant_application
    client.force_login(user)

    upload = SimpleUploadedFile("virus.exe", b"MZ", content_type="application/octet-stream")

    response = client.post(
        reverse("consultant_document_upload", args=[application.pk]),
        {"file": upload, "next": reverse("dashboard")},
        follow=True,
    )

    assert response.status_code == 200
    assert Document.objects.filter(application=application).count() == 0

    messages = list(response.context["messages"])
    assert any("Unsupported file type" in message.message for message in messages)


@pytest.mark.django_db
def test_other_consultant_cannot_download_document(client, settings, tmp_path, consultant_application, user_factory):
    settings.MEDIA_ROOT = tmp_path
    owner, application = consultant_application
    document = Document.objects.create(
        application=application,
        uploaded_by=owner,
        file=SimpleUploadedFile("report.pdf", b"%PDF-1.4", content_type="application/pdf"),
    )

    other_user = user_factory(username="other", role=Roles.CONSULTANT)
    client.force_login(other_user)

    response = client.get(reverse("consultant_document_download", args=[document.pk]))
    assert response.status_code == 302
    assert reverse("forbidden") in response["Location"]


@pytest.mark.django_db
def test_staff_can_delete_document(client, settings, tmp_path, consultant_application, user_factory):
    settings.MEDIA_ROOT = tmp_path
    owner, application = consultant_application
    document = Document.objects.create(
        application=application,
        uploaded_by=owner,
        file=SimpleUploadedFile("report.pdf", b"%PDF-1.4", content_type="application/pdf"),
    )
    file_path = document.file.path

    staff_user = user_factory(username="staff-user", role=Roles.STAFF)
    client.force_login(staff_user)

    response = client.post(
        reverse("consultant_document_delete", args=[document.pk]),
        {"next": reverse("staff_consultant_detail", args=[application.pk])},
    )

    assert response.status_code == 302
    assert not Document.objects.filter(pk=document.pk).exists()
    assert not os.path.exists(file_path)
