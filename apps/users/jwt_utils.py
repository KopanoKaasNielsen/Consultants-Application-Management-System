"""Utilities for decoding and validating JWT bearer tokens."""

from __future__ import annotations

from typing import Iterable, Sequence, Set

import jwt
from django.conf import settings
from jwt import InvalidTokenError

from apps.users.constants import UserRole


class JWTValidationError(Exception):
    """Raised when a JWT token cannot be decoded or validated."""


def _normalise_algorithms(value: Iterable[str] | str | None) -> Sequence[str]:
    if not value:
        return ("HS256",)

    if isinstance(value, str):
        return (value,)

    return tuple(value)


def extract_bearer_token(auth_header: str | None) -> str | None:
    """Return the JWT token from a standard ``Authorization`` header."""

    if not auth_header:
        return None

    parts = auth_header.split()
    if len(parts) != 2:
        return None

    prefix, token = parts
    if prefix.lower() != "bearer" or not token:
        return None

    return token


def decode_roles(token: str) -> Set[UserRole]:
    """Decode ``token`` and return the declared roles as :class:`UserRole`."""

    if not token:
        raise JWTValidationError("Bearer token is missing.")

    secret = getattr(settings, "JWT_AUTH_SECRET", None) or settings.SECRET_KEY
    algorithms = _normalise_algorithms(
        getattr(settings, "JWT_AUTH_ALGORITHMS", None)
        or getattr(settings, "JWT_AUTH_ALGORITHM", None)
    )

    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=list(algorithms),
            options={"verify_aud": False},
        )
    except InvalidTokenError as exc:  # pragma: no cover - delegated to jwt
        raise JWTValidationError("Invalid JWT token") from exc

    raw_roles = payload.get("roles")
    if raw_roles is None:
        return set()

    if isinstance(raw_roles, (list, tuple, set)):
        role_values = raw_roles
    else:
        role_values = [raw_roles]

    roles: Set[UserRole] = set()
    for role in role_values:
        if isinstance(role, UserRole):
            roles.add(role)
            continue
        if not isinstance(role, str):
            raise JWTValidationError("Roles claim must contain strings.")
        try:
            roles.add(UserRole(role.lower()))
        except ValueError as exc:
            raise JWTValidationError(f"Unknown role: {role}") from exc

    return roles


def roles_from_authorization_header(auth_header: str | None) -> Set[UserRole]:
    """Decode the provided ``Authorization`` header and return the roles."""

    token = extract_bearer_token(auth_header)
    if not token:
        return set()

    return decode_roles(token)
