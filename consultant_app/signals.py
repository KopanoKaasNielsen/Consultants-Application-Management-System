"""Custom signals for consultant certificate notifications."""
from __future__ import annotations

from typing import Any, Mapping

from django.apps import apps
from django.dispatch import Signal, receiver


certificate_notification_dispatched = Signal()


@receiver(certificate_notification_dispatched)
def record_certificate_notification_log(
    sender: object,
    *,
    consultant_id: int,
    event: str,
    channel: str,
    status: str,
    certificate_id: int | None = None,
    reason: str | None = None,
    actor_id: int | None = None,
    metadata: Mapping[str, Any] | None = None,
    error: BaseException | None = None,
    **_: Any,
) -> None:
    """Persist a log entry for certificate notification activity."""

    LogEntry = apps.get_model("consultants", "LogEntry")

    context: dict[str, Any] = {
        "action": f"certificate.notification.{event}",
        "channel": channel,
        "status": status,
        "consultant_id": consultant_id,
    }
    if certificate_id is not None:
        context["certificate_id"] = certificate_id
    if reason:
        context["reason"] = reason
    if metadata:
        context["metadata"] = dict(metadata)
    if error is not None:
        context["error"] = str(error)

    level = "INFO" if status == "sent" else "WARNING"
    message = (
        f"{channel.upper()} notification for certificate {event} {status}".strip()
    )

    LogEntry.objects.create(
        logger_name="consultant_app.notifications",
        level=level,
        message=message,
        user_id=actor_id,
        context=context,
    )


__all__ = ["certificate_notification_dispatched"]
