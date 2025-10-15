"""DRF permission classes aligned with the application's role model."""

from __future__ import annotations

from typing import Type

from rest_framework.permissions import BasePermission

from apps.users.constants import UserRole
from apps.users.permissions import user_has_role


class _RolePermission(BasePermission):
    """Base class delegating permission checks to ``user_has_role``."""

    role: UserRole

    def has_permission(self, request, view):  # type: ignore[override]
        user = request.user
        return user_has_role(user, self.role)


class IsAdminUserRole(_RolePermission):
    """Allow access to users mapped to the Admin role."""

    role = UserRole.ADMIN


class IsStaffUserRole(_RolePermission):
    """Allow access to users mapped to the Staff role."""

    role = UserRole.STAFF


class IsBoardUserRole(_RolePermission):
    """Allow access to users mapped to the Board role."""

    role = UserRole.BOARD


class IsConsultantUserRole(_RolePermission):
    """Allow access to users mapped to the Consultant role."""

    role = UserRole.CONSULTANT


ROLE_PERMISSION_MAP: dict[UserRole, Type[_RolePermission]] = {
    UserRole.ADMIN: IsAdminUserRole,
    UserRole.STAFF: IsStaffUserRole,
    UserRole.BOARD: IsBoardUserRole,
    UserRole.CONSULTANT: IsConsultantUserRole,
}
"""Convenience mapping of roles to their associated permission classes."""
