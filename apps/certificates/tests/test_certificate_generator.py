import pytest
from django.urls import reverse
from django.contrib.auth.models import User, Group
from django.utils import timezone
from apps.certificates.models import Certificate
from apps.certificates.forms import CertificateForm
from apps.certificates.services.generator import generate_certificate_pdf

pytestmark = pytest.mark.django_db


@pytest.fixture
def data_clack_officer():
    user = User.objects.create_user(username="officer", password="pass123")
    group, _ = Group.objects.get_or_create(name="Data Clack Officer")
    user.groups.add(group)
    return user


def test_certificate_form_defaults():
    form = CertificateForm()
    assert "valid_until" in form.fields
    assert form.fields["valid_until"].initial is not None


def test_generate_certificate_pdf_returns_pdf(data_clack_officer):
    cert = Certificate.objects.create(
        consultant=data_clack_officer,
        valid_until=timezone.now().date(),
        remarks="Testing PDF",
        quick_issue=True,
    )
    response = generate_certificate_pdf(cert)
    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"


def test_certificate_view_requires_role(client):
    url = reverse("certificates:generate")
    resp = client.get(url)
    assert resp.status_code in (302, 403)


def test_certificate_view_allows_data_clack_officer(client, data_clack_officer):
    client.login(username="officer", password="pass123")
    url = reverse("certificates:generate")
    resp = client.get(url)
    assert resp.status_code == 200
