import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from apps.users.constants import ROLE_GROUP_MAP, UserRole as Roles

User = get_user_model()

@pytest.fixture
def user_factory(db):
    def create_user(username="testuser", role=Roles.CONSULTANT):
        user = User.objects.create_user(username=username, password="password123")
        user.role = role
        user.save()

        for group_name in ROLE_GROUP_MAP.get(role, set()):
            group, _ = Group.objects.get_or_create(name=group_name)
            user.groups.add(group)

        return user
    return create_user
