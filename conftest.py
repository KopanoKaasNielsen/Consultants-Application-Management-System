import os

import pytest


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings.dev")

import django  # noqa: E402

django.setup()


from django.contrib.auth import get_user_model  # noqa: E402
from django.contrib.auth.models import Group  # noqa: E402

from apps.users.constants import (  # noqa: E402
    ADMINS_GROUP_NAME,
    ROLE_GROUP_MAP,
    UserRole as Roles,
)


User = get_user_model()


@pytest.fixture
def user_factory(db):
    def create_user(username="testuser", role=Roles.CONSULTANT):
        user = User.objects.create_user(username=username, password="password123")

        for group_name in ROLE_GROUP_MAP.get(role, set()):
            if role == Roles.STAFF and group_name == ADMINS_GROUP_NAME:
                continue
            group, _ = Group.objects.get_or_create(name=group_name)
            user.groups.add(group)

        if role in {Roles.ADMIN, Roles.STAFF}:
            user.is_staff = True
        if role == Roles.ADMIN:
            user.is_superuser = True

        if user.is_staff or user.is_superuser:
            user.save(update_fields=["is_staff", "is_superuser"])

        return user

    return create_user
