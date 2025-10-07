import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.consultants.forms import ConsultantForm

from tests.utils import consultant_form_data, consultant_form_files


@pytest.mark.django_db
def test_consultant_form_requires_documents_on_submit():
    data = consultant_form_data()
    files = consultant_form_files()
    files.pop("cv")

    form = ConsultantForm(data=data, files=files)

    assert not form.is_valid()
    assert "This document is required." in form.errors["cv"]


@pytest.mark.django_db
def test_consultant_form_allows_draft_without_documents():
    data = consultant_form_data(action="draft")
    form = ConsultantForm(data=data)

    assert form.is_valid()


@pytest.mark.django_db
def test_consultant_form_rejects_invalid_file_type():
    data = consultant_form_data()
    files = consultant_form_files(
        id_document=SimpleUploadedFile(
            "id.txt", b"text content", content_type="text/plain"
        )
    )

    form = ConsultantForm(data=data, files=files)

    assert not form.is_valid()
    assert "Only PDF, JPG, or PNG files are allowed." in form.errors["id_document"]
