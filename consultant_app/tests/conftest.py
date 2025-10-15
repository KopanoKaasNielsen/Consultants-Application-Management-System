import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from apps.users.constants import STAFF_GROUP_NAMES


@pytest.fixture
def client(client):
    """Ensure consultant_app API tests default to an authenticated staff client."""
    user_model = get_user_model()
    staff_user = user_model.objects.create_user(
        username="staff-api-tester",
        email="staff-api@example.com",
        password="testpass123",
    )
    default_staff_group = "Staff" if "Staff" in STAFF_GROUP_NAMES else next(iter(STAFF_GROUP_NAMES))
    staff_group, _ = Group.objects.get_or_create(name=default_staff_group)
    staff_user.groups.add(staff_group)
    client.force_login(staff_user)
    return client
