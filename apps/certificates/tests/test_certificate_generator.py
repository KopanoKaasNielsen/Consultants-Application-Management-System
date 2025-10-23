import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse
from django.utils import timezone

from apps.certificates.forms import CertificateForm
from apps.certificates.models import Certificate
from apps.certificates.services.generator import generate_certificate_pdf

pytestmark = pytest.mark.django_db


@pytest.fixture
def data_clack_officer():
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="officer",
        password="pass123",
        first_name="Data",
        last_name="Officer",
    )
    group, _ = Group.objects.get_or_create(name="Data Clack Officer")
    user.groups.add(group)
    return user


def test_certificate_form_defaults():
    form = CertificateForm()
    assert "valid_until" in form.fields
    assert form.fields["valid_until"].initial is not None


def test_generate_certificate_pdf_returns_pdf(data_clack_officer):
    certificate = Certificate.objects.create(
        consultant=data_clack_officer,
        valid_until=timezone.now().date(),
        remarks="Testing PDF",
        quick_issue=True,
    )
    response = generate_certificate_pdf(certificate)

    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    content_disposition = response["Content-Disposition"]
    assert f"certificate_{certificate.certificate_number}.pdf" in content_disposition


def test_certificate_view_requires_role(client):
    url = reverse("certificates:generate")

    response = client.get(url)

    assert response.status_code in (302, 403)


def test_certificate_view_allows_data_clack_officer(client, data_clack_officer):
    client.login(username="officer", password="pass123")
    url = reverse("certificates:generate")

    response = client.get(url)

    assert response.status_code == 200
    assert "form" in response.context
    assert isinstance(response.context["form"], CertificateForm)
