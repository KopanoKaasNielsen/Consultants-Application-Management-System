import pytest
from django.contrib.auth import get_user_model
from apps.users.constants import UserRole as Roles

User = get_user_model()

@pytest.fixture
def user_factory(db):
    def create_user(username="testuser", role=Roles.CONSULTANT):
        user = User.objects.create_user(username=username, password="password123")
        user.role = role  # or assign user.groups.add(...) if using Django groups
        user.save()
        return user
    return create_user
