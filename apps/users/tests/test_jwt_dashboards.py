"""Tests for JWT-authenticated dashboard routing."""

from __future__ import annotations

import jwt
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.users.constants import UserRole


@pytest.fixture
def jwt_config(settings):
    settings.JWT_AUTH_SECRET = "test-secret"
    settings.JWT_AUTH_ALGORITHM = "HS256"
    settings.JWT_AUTH_ALGORITHMS = None
    return settings


@pytest.fixture
def user(db):
    return get_user_model().objects.create_user(
        username="jwt-user", email="jwt@example.com", password="password123"
    )


def _token(settings, role: UserRole) -> str:
    return jwt.encode(
        {"roles": [role.value]},
        settings.JWT_AUTH_SECRET,
        algorithm=settings.JWT_AUTH_ALGORITHM,
    )


@pytest.mark.django_db
def test_board_token_redirects_to_decisions_dashboard(client, jwt_config, user):
    client.force_login(user)
    token = _token(jwt_config, UserRole.BOARD)

    response = client.get(
        reverse("dashboard"),
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )

    assert response.status_code == 302
    assert response.url == reverse("decisions_dashboard")

    decisions_response = client.get(
        response.url,
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )
    assert decisions_response.status_code == 200


@pytest.mark.django_db
def test_staff_token_redirects_to_vetting_dashboard(client, jwt_config, user):
    client.force_login(user)
    token = _token(jwt_config, UserRole.STAFF)

    response = client.get(
        reverse("dashboard"),
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )

    assert response.status_code == 302
    assert response.url == reverse("vetting_dashboard")

    vetting_response = client.get(
        response.url,
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )
    assert vetting_response.status_code == 200


@pytest.mark.django_db
def test_consultant_token_receives_consultant_dashboard(client, jwt_config, user):
    client.force_login(user)
    token = _token(jwt_config, UserRole.CONSULTANT)

    response = client.get(
        reverse("dashboard"),
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )

    assert response.status_code == 200
    template_names = {template.name for template in response.templates if template.name}
    assert "dashboard.html" in template_names


@pytest.mark.django_db
def test_consultant_group_access_without_jwt(client, user_factory):
    user = user_factory(role=UserRole.CONSULTANT)
    client.force_login(user)

    response = client.get(reverse("dashboard"))

    assert response.status_code == 200
    template_names = {template.name for template in response.templates if template.name}
    assert "dashboard.html" in template_names


@pytest.mark.django_db
def test_staff_group_redirects_without_jwt(client, user_factory):
    user = user_factory(role=UserRole.STAFF)
    client.force_login(user)

    response = client.get(reverse("dashboard"))

    assert response.status_code == 302
    assert response.url == reverse("vetting_dashboard")


@pytest.mark.django_db
def test_staff_group_access_allows_empty_bearer_header(client, user_factory):
    user = user_factory(role=UserRole.STAFF)
    client.force_login(user)

    response = client.get(
        reverse("vetting_dashboard"),
        HTTP_AUTHORIZATION="Bearer",
    )

    assert response.status_code == 200
