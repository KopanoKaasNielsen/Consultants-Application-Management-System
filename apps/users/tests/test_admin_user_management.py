import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.security.models import AuditLog
from apps.users.constants import (
    ADMINS_GROUP_NAME,
    CONSULTANTS_GROUP_NAME,
    UserRole,
    groups_for_roles,
)


@pytest.mark.django_db
def test_admin_can_create_user_and_assign_roles(client, user_factory):
    admin = user_factory(username="role-admin", role=UserRole.ADMIN)
    client.force_login(admin)

    response = client.post(
        reverse("admin_dashboard"),
        {
            "form": "create_user",
            "username": "newstaff",
            "first_name": "New",
            "last_name": "Staff",
            "email": "newstaff@example.com",
            "password1": "ComplexPass123",
            "password2": "ComplexPass123",
            "roles": [UserRole.STAFF.value, UserRole.CONSULTANT.value],
        },
    )

    assert response.status_code == 302

    user_model = get_user_model()
    created_user = user_model.objects.get(username="newstaff")
    assert created_user.is_staff is True
    assert created_user.is_superuser is False

    group_names = set(created_user.groups.values_list("name", flat=True))
    expected_groups = groups_for_roles([UserRole.STAFF, UserRole.CONSULTANT])
    expected_groups.discard(ADMINS_GROUP_NAME)
    assert CONSULTANTS_GROUP_NAME in group_names
    assert ADMINS_GROUP_NAME not in group_names
    assert expected_groups.issubset(group_names)

    audit_entry = AuditLog.objects.filter(
        action_code=AuditLog.ActionCode.CREATE_USER, target="newstaff"
    ).first()
    assert audit_entry is not None
    assert set(audit_entry.context.get("roles", [])) == {
        UserRole.STAFF.value,
        UserRole.CONSULTANT.value,
    }


@pytest.mark.django_db
def test_non_admin_cannot_create_users(client, user_factory):
    staff_user = user_factory(username="role-staff", role=UserRole.STAFF)
    client.force_login(staff_user)

    response = client.post(
        reverse("admin_dashboard"),
        {
            "form": "create_user",
            "username": "blocked",
            "password1": "ComplexPass123",
            "password2": "ComplexPass123",
            "roles": [UserRole.CONSULTANT.value],
        },
    )

    assert response.status_code in [302, 403]
    if response.status_code == 302:
        assert "/forbidden" in response.url
    user_model = get_user_model()
    assert not user_model.objects.filter(username="blocked").exists()


@pytest.mark.django_db
def test_invalid_submission_renders_errors(client, user_factory):
    admin = user_factory(username="role-admin-errors", role=UserRole.ADMIN)
    client.force_login(admin)

    response = client.post(
        reverse("admin_dashboard"),
        {
            "form": "create_user",
            "username": "invalid",
            "password1": "ComplexPass123",
            "password2": "ComplexPass123",
        },
    )

    assert response.status_code == 200
    assert "This field is required." in response.content.decode()
    user_model = get_user_model()
    assert not user_model.objects.filter(username="invalid").exists()
