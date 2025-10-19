"""Middleware for attaching JWT-derived role information to requests."""

from __future__ import annotations

from typing import Set

from apps.users.constants import UserRole
from apps.users.jwt_utils import (
    JWTValidationError,
    decode_roles,
    extract_bearer_token,
)
from apps.users.permissions import user_has_role


class JWTAuthenticationMiddleware:
    """Decode bearer tokens and expose their roles on the request object."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        roles, token_present = self._resolve_roles(request)
        request.jwt_roles = roles
        request.jwt_token_present = token_present
        return self.get_response(request)

    def _resolve_roles(self, request) -> tuple[Set[UserRole], bool]:
        auth_header = request.META.get("HTTP_AUTHORIZATION")
        if auth_header:
            token = extract_bearer_token(auth_header)
            if not token:
                return set(), False
            try:
                return decode_roles(token), True
            except JWTValidationError:
                return set(), False

        user = getattr(request, "user", None)
        if getattr(user, "is_authenticated", False):
            derived_roles = {
                role
                for role in UserRole
                if user_has_role(user, role)
            }
            if derived_roles:
                return derived_roles, False

        return set(), False
