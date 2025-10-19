"""Regression tests for the role-based throttling rules."""

from __future__ import annotations

import uuid

import jwt
import pytest
from django.conf import settings
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.users.constants import (
    ADMINS_GROUP_NAME,
    BACKOFFICE_GROUP_NAME,
    BOARD_COMMITTEE_GROUP_NAME,
    CONSULTANTS_GROUP_NAME,
    UserRole,
)


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user_factory(django_user_model):
    def _create(*group_names: str):
        user = django_user_model.objects.create_user(
            f"user-{uuid.uuid4().hex[:8]}",
            password="password123",
        )
        for name in group_names:
            group, _ = Group.objects.get_or_create(name=name)
            user.groups.add(group)
        return user

    return _create


def _role_token(role: UserRole) -> str:
    payload = {"roles": [role.value]}
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
    if isinstance(token, bytes):
        token = token.decode("utf-8")
    return token


@pytest.mark.django_db
def test_consultant_requests_are_limited(api_client):
    url = reverse("api:consultant-validate")
    token = _role_token(UserRole.CONSULTANT)
    headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    for _ in range(60):
        response = api_client.post(url, {"email": "unique@example.com"}, format="json", **headers)
        assert response.status_code == status.HTTP_200_OK

    response = api_client.post(url, {"email": "unique@example.com"}, format="json", **headers)
    assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS


@pytest.mark.django_db
def test_staff_dashboard_rate_limit(api_client, user_factory):
    user = user_factory(BACKOFFICE_GROUP_NAME)
    api_client.force_authenticate(user=user)
    url = reverse("api:staff-consultants-list")

    for _ in range(30):
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK

    response = api_client.get(url)
    assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS


@pytest.mark.django_db
def test_board_tokens_use_board_rate(api_client):
    url = reverse("api:consultant-validate")
    token = _role_token(UserRole.BOARD)
    headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    for _ in range(15):
        response = api_client.post(url, {"email": "board@example.com"}, format="json", **headers)
        assert response.status_code == status.HTTP_200_OK

    response = api_client.post(url, {"email": "board@example.com"}, format="json", **headers)
    assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS


@pytest.mark.django_db
def test_admin_requests_are_unlimited(api_client, user_factory):
    user = user_factory(ADMINS_GROUP_NAME)
    api_client.force_authenticate(user=user)
    url = reverse("api:staff-logs-list")

    for _ in range(40):
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK

    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_consultant_group_users_apply_consultant_rate(api_client, user_factory):
    user = user_factory(CONSULTANTS_GROUP_NAME)
    api_client.force_authenticate(user=user)
    url = reverse("api:consultant-validate")

    for _ in range(60):
        response = api_client.post(url, {"email": "group@example.com"}, format="json")
        assert response.status_code == status.HTTP_200_OK

    response = api_client.post(url, {"email": "group@example.com"}, format="json")
    assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS


@pytest.mark.django_db
def test_board_group_users_apply_board_rate(api_client, user_factory):
    user = user_factory(BOARD_COMMITTEE_GROUP_NAME)
    api_client.force_authenticate(user=user)
    url = reverse("api:consultant-validate")

    for _ in range(15):
        response = api_client.post(url, {"email": "committee@example.com"}, format="json")
        assert response.status_code == status.HTTP_200_OK

    response = api_client.post(url, {"email": "committee@example.com"}, format="json")
    assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
