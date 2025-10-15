"""Compatibility exports for legacy imports within the users app."""

from apps.security.models import AuditLog

__all__ = ["AuditLog"]
