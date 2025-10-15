"""Celery tasks supporting security monitoring workflows."""

from __future__ import annotations

import json
import logging
from typing import Any

from celery import shared_task
from django.utils import timezone

from utils.alert_notifier import AlertMessage, send_security_alert

from .models import AuditLog


LOGGER = logging.getLogger(__name__)


def _build_alert_message(log: AuditLog) -> AlertMessage:
    """Create a rich alert message for a given audit log entry."""

    context: dict[str, Any] = dict(log.context or {})
    severity = str(context.get("severity", "critical")).lower()

    metadata = {
        "action": log.get_action_code_display(),
        "timestamp": timezone.localtime(log.timestamp).isoformat(),
        "endpoint": log.endpoint or "n/a",
        "client_ip": log.client_ip or "n/a",
    }

    if log.user:
        metadata["user"] = log.user.get_username()
    if log.target:
        metadata["target"] = log.target
    if context.get("failure_count"):
        metadata["failure_count"] = context.get("failure_count")
    if context.get("status_code"):
        metadata["status_code"] = context.get("status_code")

    title = f"Critical security event: {log.action_code.replace('_', ' ').title()}"
    body_lines = [
        "A high severity security event was recorded by the system.",
        "",
        f"Action: {log.get_action_code_display()}",
        f"Recorded: {timezone.localtime(log.timestamp).strftime('%Y-%m-%d %H:%M:%S %Z')}",
    ]

    if log.user:
        body_lines.append(f"User: {log.user.get_username()}")
    if log.target:
        body_lines.append(f"Target: {log.target}")
    if log.endpoint:
        body_lines.append(f"Endpoint: {log.endpoint}")
    if log.client_ip:
        body_lines.append(f"Client IP: {log.client_ip}")
    if context:
        body_lines.append("Context: " + json.dumps(context, sort_keys=True))

    body = "\n".join(body_lines)

    return AlertMessage(title=title, body=body, severity=severity or "critical", metadata=metadata)


@shared_task(name="apps.security.tasks.send_audit_log_alert")
def send_audit_log_alert(audit_log_id: int) -> None:
    """Send an alert for the specified audit log entry."""

    try:
        log = AuditLog.objects.select_related("user").get(pk=audit_log_id)
    except AuditLog.DoesNotExist:  # pragma: no cover - defensive guard
        LOGGER.warning("AuditLog %s no longer exists; skipping alert", audit_log_id)
        return

    alert = _build_alert_message(log)
    send_security_alert(alert)

