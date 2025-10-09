"""Utility helpers for writing audit log entries."""

from __future__ import annotations

from typing import Any, Mapping, Optional

from django.contrib.auth.models import AbstractBaseUser
from django.utils.functional import Promise
from django.utils.encoding import force_str

from .models import AuditLog


def _serialise_metadata(metadata: Optional[Mapping[str, Any]]) -> dict:
    """Convert metadata values to JSON-serialisable primitives."""

    if not metadata:
        return {}

    serialised: dict[str, Any] = {}
    for key, value in metadata.items():
        if isinstance(value, Promise):
            value = force_str(value)
        elif isinstance(value, (list, tuple)):
            value = [force_str(item) if isinstance(item, Promise) else item for item in value]
        serialised[key] = value
    return serialised


def log_audit_event(
    user: Optional[AbstractBaseUser],
    action_type: str,
    *,
    target_object: str = "",
    metadata: Optional[Mapping[str, Any]] = None,
) -> Optional[AuditLog]:
    """Persist an audit log entry for the supplied user.

    Anonymous or unauthenticated users are ignored so that the helper can be
    called defensively from any view without additional guards.
    """

    if user is None or not getattr(user, "is_authenticated", False):
        return None

    return AuditLog.objects.create(
        user=user,
        action_type=action_type,
        target_object=target_object,
        metadata=_serialise_metadata(metadata),
    )


__all__ = ["log_audit_event"]
