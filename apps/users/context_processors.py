"""Context helpers exposing role information to templates."""

from __future__ import annotations

from typing import Dict

from django.http import HttpRequest

from apps.users.constants import UserRole
from apps.users.permissions import user_has_role


def role_flags(request: HttpRequest) -> Dict[str, object]:
    """Expose role-aware navigation flags for the authenticated user."""

    user = getattr(request, "user", None)
    is_authenticated = getattr(user, "is_authenticated", False)

    def _has(role: UserRole) -> bool:
        if not is_authenticated:
            return False
        return user_has_role(user, role)

    has_admin_role = _has(UserRole.ADMIN)
    has_board_role = _has(UserRole.BOARD)
    has_staff_role = _has(UserRole.STAFF)
    has_consultant_role = _has(UserRole.CONSULTANT)

    return {
        "has_admin_role": has_admin_role,
        "has_board_role": has_board_role,
        "has_staff_role": has_staff_role,
        "has_consultant_role": has_consultant_role,
        "user_roles": {
            role
            for role, is_active in {
                UserRole.ADMIN.value: has_admin_role,
                UserRole.BOARD.value: has_board_role,
                UserRole.STAFF.value: has_staff_role,
                UserRole.CONSULTANT.value: has_consultant_role,
            }.items()
            if is_active
        },
    }
