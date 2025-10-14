"""Regression tests for consultant certificate admin actions."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from django.contrib import messages
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import RequestFactory
from django.utils import timezone

from apps.consultants import admin as consultant_admin_module
from apps.consultants.admin import ConsultantAdmin
from apps.consultants.models import Consultant
from consultant_app.models import Certificate


@pytest.fixture
def admin_site():
    return AdminSite()


@pytest.fixture
def request_factory():
    return RequestFactory()


@pytest.fixture
def staff_admin_user(db):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="certificate-admin",
        email="certificate-admin@example.com",
        password="admin-pass-123",
        is_staff=True,
        is_superuser=True,
    )
    return user


@pytest.fixture
def consultant_with_certificate(db):
    user_model = get_user_model()
    applicant = user_model.objects.create_user(
        username="admin-action-consultant",
        email="admin-action@example.com",
        password="safe-pass-999",
    )

    consultant = Consultant.objects.create(
        user=applicant,
        full_name="Admin Action",
        id_number="ADMIN-001",
        dob=timezone.now().date(),
        gender="M",
        nationality="Kenya",
        email="admin-action@example.com",
        phone_number="0700000000",
        business_name="Admin Action Ltd",
        registration_number="REG-ADMIN",
        status="approved",
        submitted_at=timezone.now(),
    )

    issued_at = timezone.now()
    Certificate.objects.create(
        consultant=consultant,
        status=Certificate.Status.VALID,
        issued_at=issued_at,
        status_set_at=issued_at,
        valid_at=issued_at,
    )

    return consultant


def _build_admin(request_factory, admin_site):
    admin_instance = ConsultantAdmin(Consultant, admin_site)

    captured_messages: list[tuple[str, int]] = []

    def _capture_message(
        request,
        message,
        level=messages.INFO,
        extra_tags="",
        fail_silently=False,
    ):
        captured_messages.append((message, level))

    admin_instance.message_user = _capture_message  # type: ignore[method-assign]
    return admin_instance, captured_messages


@pytest.mark.django_db
def test_admin_revoke_action_dispatches_task(
    request_factory,
    admin_site,
    staff_admin_user,
    consultant_with_certificate,
    monkeypatch,
):
    admin_instance, messages = _build_admin(request_factory, admin_site)
    delay_mock = MagicMock()
    monkeypatch.setattr(
        consultant_admin_module.revoke_certificate_task,
        "delay",
        delay_mock,
    )

    request = request_factory.post("/admin/consultants/consultant/", {"reason": "Because"})
    request.user = staff_admin_user

    queryset = Consultant.objects.filter(pk=consultant_with_certificate.pk)
    admin_instance.action_mark_certificate_revoked(request, queryset)

    delay_mock.assert_called_once()
    args, kwargs = delay_mock.call_args
    assert args == (consultant_with_certificate.pk,)
    assert kwargs["reason"] == "Because"
    assert kwargs["actor_id"] == staff_admin_user.pk
    assert kwargs["notify_consultant"] is True
    assert kwargs["metadata"] == {
        "source": "admin",
        "admin_action": "ConsultantAdmin.revoked",
    }

    assert any("Successfully updated" in message for message, _ in messages)


@pytest.mark.django_db
def test_admin_reissue_action_dispatches_task(
    request_factory,
    admin_site,
    staff_admin_user,
    consultant_with_certificate,
    monkeypatch,
):
    admin_instance, messages = _build_admin(request_factory, admin_site)
    delay_mock = MagicMock()
    monkeypatch.setattr(
        consultant_admin_module.reissue_certificate_task,
        "delay",
        delay_mock,
    )

    request = request_factory.post(
        "/admin/consultants/consultant/",
        {"reason": "Refresh certificate"},
    )
    request.user = staff_admin_user

    queryset = Consultant.objects.filter(pk=consultant_with_certificate.pk)
    admin_instance.action_mark_certificate_reissued(request, queryset)

    delay_mock.assert_called_once()
    args, kwargs = delay_mock.call_args
    assert args == (consultant_with_certificate.pk,)
    assert kwargs["reason"] == "Refresh certificate"
    assert kwargs["actor_id"] == staff_admin_user.pk
    assert kwargs["notify_consultant"] is True
    assert kwargs["metadata"] == {
        "source": "admin",
        "admin_action": "ConsultantAdmin.reissued",
    }

    assert any("Successfully updated" in message for message, _ in messages)


@pytest.mark.django_db
def test_admin_action_requires_reason(
    request_factory,
    admin_site,
    staff_admin_user,
    consultant_with_certificate,
    monkeypatch,
):
    admin_instance, messages = _build_admin(request_factory, admin_site)
    monkeypatch.setattr(
        consultant_admin_module.revoke_certificate_task,
        "delay",
        MagicMock(),
    )

    request = request_factory.post("/admin/consultants/consultant/", {"reason": "  "})
    request.user = staff_admin_user

    queryset = Consultant.objects.filter(pk=consultant_with_certificate.pk)
    admin_instance.action_mark_certificate_revoked(request, queryset)

    consultant_admin_module.revoke_certificate_task.delay.assert_not_called()
    assert any("Please provide a reason" in message for message, _ in messages)


@pytest.mark.django_db
def test_admin_action_warns_for_missing_certificate(
    request_factory,
    admin_site,
    staff_admin_user,
    monkeypatch,
):
    admin_instance, messages = _build_admin(request_factory, admin_site)
    delay_mock = MagicMock()
    monkeypatch.setattr(
        consultant_admin_module.revoke_certificate_task,
        "delay",
        delay_mock,
    )

    user_model = get_user_model()
    applicant = user_model.objects.create_user(
        username="no-certificate-consultant",
        email="no-certificate@example.com",
        password="safe-pass-321",
    )
    consultant = Consultant.objects.create(
        user=applicant,
        full_name="No Certificate",
        id_number="ADMIN-404",
        dob=timezone.now().date(),
        gender="F",
        nationality="Kenya",
        email="no-certificate@example.com",
        phone_number="0700000001",
        business_name="Missing Certificate Co",
        registration_number="REG-NONE",
        status="approved",
        submitted_at=timezone.now(),
    )

    request = request_factory.post("/admin/consultants/consultant/", {"reason": "Check"})
    request.user = staff_admin_user

    queryset = Consultant.objects.filter(pk=consultant.pk)
    admin_instance.action_mark_certificate_revoked(request, queryset)

    delay_mock.assert_not_called()
    assert any("no certificate to update" in message.lower() for message, _ in messages)
