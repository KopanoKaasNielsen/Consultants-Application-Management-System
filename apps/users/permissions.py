"""Helpers for working with user roles and permissions."""

from __future__ import annotations

from functools import wraps
from typing import Iterable, Union

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from .constants import ROLE_GROUP_MAP, UserRole, groups_for_roles


RoleLike = Union[UserRole, str]


def _normalise_role(role: RoleLike) -> UserRole:
    if isinstance(role, UserRole):
        return role

    if isinstance(role, str):
        try:
            return UserRole(role)
        except ValueError:
            try:
                return UserRole(role.lower())
            except ValueError as exc:  # pragma: no cover - defensive branch
                raise KeyError(f"Unknown role: {role}") from exc

    raise TypeError(f"Role must be a UserRole or string, got {type(role)!r}")


def user_has_role(user, role: RoleLike) -> bool:
    """Return ``True`` if the user belongs to any group mapped to ``role``."""

    if not getattr(user, "is_authenticated", False):
        return False

    if getattr(user, "is_superuser", False):
        return True

    normalised_role = _normalise_role(role)
    role_groups = ROLE_GROUP_MAP.get(normalised_role, set())
    if not role_groups:
        return False

    return user.groups.filter(name__in=role_groups).exists()


def user_has_any_role(user, roles: Iterable[RoleLike]) -> bool:
    """Return ``True`` if the user matches any of the provided roles."""

    return any(user_has_role(user, role) for role in roles)


def role_required(*roles: RoleLike):
    """Decorator ensuring the current user matches at least one role."""

    if not roles:
        raise ValueError("role_required must be provided at least one role")

    normalised_roles = tuple(_normalise_role(role) for role in roles)
    allowed_groups = groups_for_roles(normalised_roles)

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            user = request.user

            if getattr(user, "is_superuser", False):
                return view_func(request, *args, **kwargs)

            request_roles = getattr(request, "jwt_roles", None)
            token_present = getattr(request, "jwt_token_present", False)
            if request_roles is not None and (token_present or request_roles):
                if any(role in request_roles for role in normalised_roles):
                    return view_func(request, *args, **kwargs)
                raise PermissionDenied

            if not user.groups.filter(name__in=allowed_groups).exists():
                raise PermissionDenied

            return view_func(request, *args, **kwargs)

        return login_required(_wrapped)

    return decorator
