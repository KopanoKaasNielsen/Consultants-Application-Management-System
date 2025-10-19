"""Integration tests for the audit log API endpoint."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.security.models import AuditLog
from apps.users.constants import (
    BACKOFFICE_GROUP_NAME,
    BOARD_COMMITTEE_GROUP_NAME,
    CONSULTANTS_GROUP_NAME,
    UserRole as Roles,
)

User = get_user_model()


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.mark.django_db
def test_admin_can_list_audit_logs(api_client: APIClient, user_factory):
    admin = user_factory(username="admin-user", role=Roles.ADMIN)
    actor = user_factory(username="staff-user", role=Roles.STAFF)

    log_one = AuditLog.objects.create(
        user=admin,
        resolved_role=Roles.ADMIN.value,
        action_code=AuditLog.ActionCode.LOGIN_SUCCESS,
        target="dashboard",
        endpoint="/api/staff/consultants/",
        client_ip="127.0.0.1",
        context={"detail": "admin login"},
    )
    log_two = AuditLog.objects.create(
        user=actor,
        resolved_role=Roles.STAFF.value,
        action_code=AuditLog.ActionCode.EXPORT_CSV,
        target="consultant:42",
        endpoint="/api/staff/consultants/export/csv/",
        client_ip="192.0.2.10",
        context={"filename": "export.csv"},
    )

    api_client.force_authenticate(user=admin)
    url = reverse("api:audit-logs-list")
    response = api_client.get(url)

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["count"] == 2
    assert payload["results"]

    results_by_id = {item["id"]: item for item in payload["results"]}
    first = results_by_id[log_one.id]
    second = results_by_id[log_two.id]

    assert first["resolved_role"] == Roles.ADMIN.value
    assert first["endpoint"] == "/api/staff/consultants/"
    assert first["client_ip"] == "127.0.0.1"
    assert first["context"] == {"detail": "admin login"}
    assert first["username"] == "admin-user"
    assert first["action_display"] == AuditLog.ActionCode.LOGIN_SUCCESS.label

    assert second["resolved_role"] == Roles.STAFF.value
    assert second["target"] == "consultant:42"
    assert second["context"] == {"filename": "export.csv"}
    assert second["user_id"] == actor.id


def _user_in_group(username: str, group_name: str):
    user = User.objects.create_user(username=username, password="password123")
    group, _ = Group.objects.get_or_create(name=group_name)
    user.groups.add(group)
    return user


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("role", "group_name"),
    [
        (Roles.STAFF, BACKOFFICE_GROUP_NAME),
        (Roles.BOARD, BOARD_COMMITTEE_GROUP_NAME),
        (Roles.CONSULTANT, CONSULTANTS_GROUP_NAME),
    ],
)
def test_non_admin_roles_are_forbidden(role, group_name, api_client: APIClient):
    user = _user_in_group(username=f"{role.value}-user", group_name=group_name)
    api_client.force_authenticate(user=user)

    url = reverse("api:audit-logs-list")
    response = api_client.get(url)

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_unauthenticated_requests_are_rejected(api_client: APIClient):
    url = reverse("api:audit-logs-list")
    response = api_client.get(url)

    assert response.status_code == status.HTTP_403_FORBIDDEN
