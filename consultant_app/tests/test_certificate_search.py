from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.consultants.models import Consultant
from consultant_app.models import Certificate


@pytest.fixture
def certificate_records(db):
    user_model = get_user_model()

    user_one = user_model.objects.create_user(
        username="alice", email="alice@example.com", password="pass1234"
    )
    user_two = user_model.objects.create_user(
        username="bob", email="bob@example.com", password="pass1234"
    )

    now = timezone.now()
    earlier = now - timedelta(days=30)

    consultant_one = Consultant.objects.create(
        user=user_one,
        full_name="Alice Example",
        id_number="ID-100",
        dob=timezone.now().date(),
        gender="F",
        nationality="Kenya",
        email="alice@example.com",
        phone_number="0710000000",
        business_name="Alice Consulting",
        status="approved",
        submitted_at=now,
    )
    consultant_two = Consultant.objects.create(
        user=user_two,
        full_name="Bob Sample",
        id_number="ID-200",
        dob=timezone.now().date(),
        gender="M",
        nationality="Kenya",
        email="bob@example.com",
        phone_number="0720000000",
        business_name="Sample Advisory",
        status="approved",
        submitted_at=earlier,
    )

    for consultant, issued_at in ((consultant_one, now), (consultant_two, earlier)):
        consultant.certificate_generated_at = issued_at
        consultant.save(update_fields=["certificate_generated_at"])

    primary = Certificate.objects.create(
        consultant=consultant_one,
        status=Certificate.Status.VALID,
        issued_at=now,
        status_set_at=now,
        valid_at=now,
    )
    secondary = Certificate.objects.create(
        consultant=consultant_two,
        status=Certificate.Status.REVOKED,
        issued_at=earlier,
        status_set_at=earlier,
        revoked_at=earlier,
    )

    return {"primary": primary, "secondary": secondary}


@pytest.mark.django_db
def test_search_certificate_by_partial_name(client, certificate_records):
    certificate = certificate_records["primary"]
    url = reverse("certificate-search")

    response = client.get(url, {"name": "alice"})

    assert response.status_code == 200
    assert response.context["search_performed"] is True
    assert response.context["result_count"] == 1

    result = response.context["results"][0]
    assert result["consultant_name"] == certificate.consultant.full_name
    assert result["certificate_id"] == str(certificate.consultant.certificate_uuid)
    assert result["issued_on"] == certificate.issued_at.date()
    assert result["status_code"] == certificate.status.upper()


@pytest.mark.django_db
def test_search_certificate_by_partial_certificate_id(client, certificate_records):
    certificate = certificate_records["primary"]
    url = reverse("certificate-search")
    partial_id = str(certificate.consultant.certificate_uuid)[:8]

    response = client.get(url, {"certificate_id": partial_id.upper()})

    assert response.status_code == 200
    assert response.context["result_count"] == 1

    result = response.context["results"][0]
    assert result["certificate_id"].startswith(partial_id)
    assert result["verification_url"].endswith(
        f"/verify/{certificate.consultant.certificate_uuid}/"
    )


@pytest.mark.django_db
def test_search_certificate_by_issue_date(client, certificate_records):
    certificate = certificate_records["secondary"]
    url = reverse("certificate-search")

    response = client.get(
        url,
        {"issue_date": certificate.issued_at.date().isoformat()},
    )

    assert response.status_code == 200
    assert response.context["result_count"] == 1
    assert response.context["results"][0]["certificate_id"] == str(
        certificate.consultant.certificate_uuid
    )


@pytest.mark.django_db
def test_search_certificate_invalid_issue_date(client, certificate_records):
    url = reverse("certificate-search")

    response = client.get(url, {"issue_date": "2024-13-40"})

    assert response.status_code == 200
    assert response.context["results"] == []
    assert response.context["result_count"] == 0
    assert response.context["form_errors"]["issue_date"] == (
        "Enter a valid date in YYYY-MM-DD format."
    )
