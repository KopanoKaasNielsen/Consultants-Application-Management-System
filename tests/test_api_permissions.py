import uuid

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse
from rest_framework.test import APIClient

from apps.users.constants import (
    ADMINS_GROUP_NAME,
    BACKOFFICE_GROUP_NAME,
    BOARD_COMMITTEE_GROUP_NAME,
    CONSULTANTS_GROUP_NAME,
)


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


@pytest.mark.django_db
@pytest.mark.parametrize(
    "group_names, expected_status",
    [
        ((BACKOFFICE_GROUP_NAME,), 200),
        ((ADMINS_GROUP_NAME,), 200),
        ((BOARD_COMMITTEE_GROUP_NAME,), 403),
        ((CONSULTANTS_GROUP_NAME,), 403),
        (tuple(), 403),
    ],
)
def test_staff_consultant_permissions(api_client, user_factory, group_names, expected_status):
    user = user_factory(*group_names)
    api_client.force_authenticate(user=user)

    url = reverse("api:staff-consultants-list")
    response = api_client.get(url)

    assert response.status_code == expected_status


@pytest.mark.django_db
@pytest.mark.parametrize(
    "group_names, expected_status",
    [
        ((BACKOFFICE_GROUP_NAME,), 200),
        ((ADMINS_GROUP_NAME,), 200),
        ((BOARD_COMMITTEE_GROUP_NAME,), 403),
        ((CONSULTANTS_GROUP_NAME,), 403),
        (tuple(), 403),
    ],
)
def test_staff_log_permissions(api_client, user_factory, group_names, expected_status):
    user = user_factory(*group_names)
    api_client.force_authenticate(user=user)

    url = reverse("api:staff-logs-list")
    response = api_client.get(url)

    assert response.status_code == expected_status
