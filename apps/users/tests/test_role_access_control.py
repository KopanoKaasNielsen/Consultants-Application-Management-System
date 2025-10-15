"""Tests covering role-based access control across key views."""

from __future__ import annotations

from urllib.parse import urlencode

import pytest
from django.urls import reverse

from apps.users.constants import UserRole


def _forbidden_target(path: str) -> str:
    return f"{reverse('forbidden')}?{urlencode({'next': path})}"


@pytest.mark.django_db
def test_admin_role_can_access_admin_dashboard(client, user_factory):
    admin_user = user_factory(username="role-admin", role=UserRole.ADMIN)
    client.force_login(admin_user)

    response = client.get(reverse("admin_dashboard"))

    assert response.status_code == 200


@pytest.mark.django_db
def test_staff_role_cannot_access_admin_dashboard(client, user_factory):
    staff_user = user_factory(username="role-staff", role=UserRole.STAFF)
    client.force_login(staff_user)

    url = reverse("admin_dashboard")
    response = client.get(url)

    assert response.status_code == 302
    assert response.url == _forbidden_target(url)


@pytest.mark.django_db
def test_superuser_can_access_service_health(client, user_factory):
    admin_user = user_factory(username="role-admin-health", role=UserRole.ADMIN)
    client.force_login(admin_user)

    response = client.get(reverse("admin_service_health"))

    assert response.status_code == 200


@pytest.mark.django_db
def test_consultant_role_redirected_from_service_health(client, user_factory):
    consultant_user = user_factory(username="role-consultant-health", role=UserRole.CONSULTANT)
    client.force_login(consultant_user)

    url = reverse("admin_service_health")
    response = client.get(url)

    assert response.status_code == 302
    assert response.url == _forbidden_target(url)


@pytest.mark.django_db
def test_board_role_can_view_board_dashboard(client, user_factory):
    board_user = user_factory(username="role-board", role=UserRole.BOARD)
    client.force_login(board_user)

    response = client.get(reverse("board_dashboard"))

    assert response.status_code == 200


@pytest.mark.django_db
def test_consultant_cannot_access_board_dashboard(client, user_factory):
    consultant = user_factory(username="role-consultant", role=UserRole.CONSULTANT)
    client.force_login(consultant)

    url = reverse("board_dashboard")
    response = client.get(url)

    assert response.status_code == 302
    assert response.url == _forbidden_target(url)


@pytest.mark.django_db
def test_staff_role_can_access_staff_dashboard(client, user_factory):
    staff_user = user_factory(username="role-staff-dashboard", role=UserRole.STAFF)
    client.force_login(staff_user)

    response = client.get(reverse("staff_dashboard"))

    assert response.status_code == 200


@pytest.mark.django_db
def test_board_role_redirected_from_staff_dashboard(client, user_factory):
    board_user = user_factory(username="role-board-staff", role=UserRole.BOARD)
    client.force_login(board_user)

    url = reverse("staff_dashboard")
    response = client.get(url)

    assert response.status_code == 302
    assert response.url == _forbidden_target(url)


@pytest.mark.django_db
def test_admin_role_can_access_impersonation_dashboard(client, user_factory):
    admin_user = user_factory(username="role-admin-impersonation", role=UserRole.ADMIN)
    client.force_login(admin_user)

    response = client.get(reverse("impersonation_dashboard"))

    assert response.status_code == 200


@pytest.mark.django_db
def test_staff_role_redirected_from_impersonation_dashboard(client, user_factory):
    staff_user = user_factory(username="role-staff-impersonation", role=UserRole.STAFF)
    client.force_login(staff_user)

    url = reverse("impersonation_dashboard")
    response = client.get(url)

    assert response.status_code == 302
    assert response.url == _forbidden_target(url)
