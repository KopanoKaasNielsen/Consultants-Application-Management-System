"""Helper functions for recording audit trail events."""

from __future__ import annotations

import logging
from contextlib import suppress
from typing import Any, Mapping, Optional

from django.contrib.auth.models import AbstractBaseUser
from django.core.exceptions import ValidationError
from django.http import HttpRequest
from django.utils.encoding import force_str
from django.utils.functional import Promise

from apps.users.constants import UserRole
from apps.users.permissions import user_has_role

from .models import AuditLog

logger = logging.getLogger(__name__)

_ROLE_PRIORITY: tuple[UserRole, ...] = (
    UserRole.ADMIN,
    UserRole.BOARD,
    UserRole.STAFF,
    UserRole.CONSULTANT,
)


def _serialise_context(context: Optional[Mapping[str, Any]]) -> dict[str, Any]:
    if not context:
        return {}

    serialised: dict[str, Any] = {}
    for key, value in context.items():
        if isinstance(value, Promise):
            value = force_str(value)
        elif isinstance(value, (list, tuple)):
            value = [force_str(item) if isinstance(item, Promise) else item for item in value]
        serialised[key] = value
    return serialised


def _derive_client_ip(request: Optional[HttpRequest]) -> Optional[str]:
    if request is None:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _resolve_user(user: Optional[AbstractBaseUser], request: Optional[HttpRequest]):
    if user is not None:
        return user
    if request is not None:
        candidate = getattr(request, "user", None)
        if getattr(candidate, "is_authenticated", False):
            return candidate
    return user


def _resolve_role(
    *, user: Optional[AbstractBaseUser], request: Optional[HttpRequest], resolved_role: Optional[str]
) -> str:
    if resolved_role:
        return resolved_role

    candidate_user = user
    if request is not None and candidate_user is None:
        request_user = getattr(request, "user", None)
        if getattr(request_user, "is_authenticated", False):
            candidate_user = request_user

    request_roles = getattr(request, "jwt_roles", None) if request is not None else None
    if request_roles:
        for role in _ROLE_PRIORITY:
            if role in request_roles:
                return role.value

    if candidate_user is not None and getattr(candidate_user, "is_authenticated", False):
        for role in _ROLE_PRIORITY:
            if user_has_role(candidate_user, role):
                return role.value
        return "unknown"

    return "anonymous"


def log_audit_event(
    *,
    action_code: str,
    request: Optional[HttpRequest] = None,
    user: Optional[AbstractBaseUser] = None,
    target: str = "",
    context: Optional[Mapping[str, Any]] = None,
    endpoint: Optional[str] = None,
    client_ip: Optional[str] = None,
    resolved_role: Optional[str] = None,
) -> AuditLog:
    """Persist an audit log entry with normalised metadata."""

    resolved_user = _resolve_user(user, request)
    role = _resolve_role(user=resolved_user, request=request, resolved_role=resolved_role)
    ip_address = client_ip or _derive_client_ip(request)
    endpoint_value = endpoint or (request.get_full_path() if request else "")

    return AuditLog.objects.create(
        user=resolved_user if getattr(resolved_user, "is_authenticated", False) else None,
        resolved_role=role,
        action_code=action_code,
        target=target,
        endpoint=endpoint_value,
        client_ip=ip_address,
        context=_serialise_context(context),
    )


def scan_uploaded_file(uploaded_file) -> None:
    """Perform lightweight scanning of uploaded files for malicious content."""

    file_descriptor = getattr(uploaded_file, "file", uploaded_file)
    initial_position = None

    try:
        if hasattr(file_descriptor, "seek") and hasattr(file_descriptor, "tell"):
            try:
                initial_position = file_descriptor.tell()
            except Exception:  # pragma: no cover - very defensive
                initial_position = None

        chunk = file_descriptor.read(4096)

        if not chunk:
            raise ValidationError("The uploaded file appears to be empty.")

        lowered = chunk.lower()
        if b"<?php" in lowered or b"<script" in lowered:
            raise ValidationError("The uploaded file contains disallowed content.")

    except ValidationError:
        raise
    except Exception:  # pragma: no cover - safety net for unexpected IO errors
        logger.exception(
            "Unable to perform malware scan on %s", getattr(uploaded_file, "name", "<unknown>")
        )
    finally:
        if hasattr(file_descriptor, "seek") and initial_position is not None:
            try:
                file_descriptor.seek(initial_position)
            except Exception:  # pragma: no cover - defensive guard
                logger.debug("Failed to reset file pointer after scan.")
        elif hasattr(uploaded_file, "seek"):
            with suppress(Exception):  # type: ignore[name-defined]
                uploaded_file.seek(0)


__all__ = ["log_audit_event", "scan_uploaded_file"]
