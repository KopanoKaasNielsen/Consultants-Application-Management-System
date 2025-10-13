"""Custom logging handlers for consultant workflows."""
from __future__ import annotations

import logging
from typing import Any, Dict

from django.contrib.auth import get_user_model

STANDARD_LOG_RECORD_ATTRS = {
    "name",
    "msg",
    "args",
    "levelname",
    "levelno",
    "pathname",
    "filename",
    "module",
    "exc_info",
    "exc_text",
    "stack_info",
    "lineno",
    "funcName",
    "created",
    "msecs",
    "relativeCreated",
    "thread",
    "threadName",
    "processName",
    "process",
}


class DatabaseLogHandler(logging.Handler):
    """Persist log records to the ``LogEntry`` database table."""

    def emit(self, record: logging.LogRecord) -> None:  # pragma: no cover - tested via integration
        from .models import LogEntry

        try:
            context = self._build_context(record)
            user = self._resolve_user(record)
            message = record.getMessage()
            level = record.levelname.upper()
            logger_name = record.name

            LogEntry.objects.create(
                logger_name=logger_name,
                level=level,
                message=message,
                user=user,
                context=context,
            )
        except Exception:  # pragma: no cover - defensive guard against logging recursion
            self.handleError(record)

    def _build_context(self, record: logging.LogRecord) -> Dict[str, Any] | None:
        provided = getattr(record, "context", None)
        context: Dict[str, Any] = {}
        if isinstance(provided, dict):
            context.update(self._serialise_mapping(provided))

        for key, value in record.__dict__.items():
            if key in STANDARD_LOG_RECORD_ATTRS or key in {"context", "user"}:
                continue
            if key.startswith("_"):
                continue
            context[key] = self._serialise(value)

        return context or None

    def _resolve_user(self, record: logging.LogRecord):
        user = getattr(record, "user", None)
        if user is not None and getattr(user, "pk", None):
            return user

        user_id = getattr(record, "user_id", None)
        if not user_id:
            return None

        UserModel = get_user_model()
        return UserModel._default_manager.filter(pk=user_id).first()

    def _serialise(self, value: Any) -> Any:
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        if isinstance(value, dict):
            return self._serialise_mapping(value)
        if isinstance(value, (list, tuple, set)):
            return [self._serialise(item) for item in value]
        if hasattr(value, "pk"):
            return value.pk
        if hasattr(value, "isoformat"):
            try:
                return value.isoformat()
            except Exception:  # pragma: no cover - fallback to string representation
                pass
        return str(value)

    def _serialise_mapping(self, mapping: Dict[str, Any]) -> Dict[str, Any]:
        return {key: self._serialise(value) for key, value in mapping.items()}


__all__ = ["DatabaseLogHandler"]
