"""Signal handlers for security audit log monitoring."""

from __future__ import annotations

import logging
from typing import Any

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import AuditLog
from .tasks import send_audit_log_alert


LOGGER = logging.getLogger(__name__)


def _is_high_severity(log: AuditLog) -> bool:
    """Determine whether the audit log entry warrants an alert."""

    context: dict[str, Any] = dict(log.context or {})
    severity = str(context.get("severity", "")).lower()
    if severity in {"critical", "high"}:
        return True

    critical_actions = getattr(
        settings,
        "SECURITY_ALERT_CRITICAL_ACTIONS",
        {AuditLog.ActionCode.CERTIFICATE_REVOKED},
    )
    if log.action_code in critical_actions:
        return True

    if log.action_code == AuditLog.ActionCode.LOGIN_FAILURE:
        failure_threshold = int(
            getattr(settings, "SECURITY_ALERT_LOGIN_FAILURE_THRESHOLD", 5)
        )
        failure_count = int(context.get("failure_count", 0) or 0)
        if failure_count >= failure_threshold:
            return True

    status_code = context.get("status_code")
    if status_code and int(status_code) >= 500:
        return True

    return False


@receiver(post_save, sender=AuditLog)
def trigger_critical_alert(sender, instance: AuditLog, created: bool, **kwargs) -> None:
    """Queue alerts for high severity audit log entries."""

    if not created:
        return

    if not _is_high_severity(instance):
        LOGGER.debug("Audit log %s does not meet alert threshold", instance.pk)
        return

    LOGGER.info(
        "Scheduling alert for audit log entry %s (%s)",
        instance.pk,
        instance.action_code,
    )
    try:
        send_audit_log_alert.delay(instance.pk)
    except Exception as exc:  # pragma: no cover - network/broker availability
        LOGGER.warning(
            "Celery broker unavailable for security alert, falling back to synchronous execution: %s",
            exc,
        )
        send_audit_log_alert.apply(args=(instance.pk,))

