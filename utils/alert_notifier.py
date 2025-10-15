"""Utility helpers for broadcasting security alerts to operators."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.mail import send_mail


LOGGER = logging.getLogger(__name__)


def _build_recipients() -> tuple[str, ...]:
    """Return the configured email recipients for security alerts."""

    recipients = getattr(settings, "SECURITY_ALERT_EMAIL_RECIPIENTS", ())
    if isinstance(recipients, (list, tuple)):
        return tuple(address for address in recipients if address)

    if isinstance(recipients, str):
        return tuple(
            address.strip()
            for address in recipients.split(",")
            if address.strip()
        )

    return tuple()


def _send_slack_notification(payload: Mapping[str, object]) -> None:
    """Send a message to the configured Slack webhook, if available."""

    webhook_url = getattr(settings, "SECURITY_ALERT_SLACK_WEBHOOK", "")
    if not webhook_url:
        LOGGER.debug("Slack webhook not configured for security alerts")
        return

    request = Request(
        webhook_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:  # pragma: no cover - network errors should not break execution
        with urlopen(request, timeout=5) as response:  # noqa: S310 - controlled URL
            response.read()
    except (HTTPError, URLError) as exc:  # pragma: no cover - logging side-effect
        LOGGER.exception("Failed to deliver security alert to Slack: %s", exc)


def _send_email_notification(subject: str, body: str) -> None:
    """Send an email notification to the configured recipients."""

    recipients = _build_recipients()
    if not recipients:
        LOGGER.debug("No email recipients configured for security alerts")
        return

    from_email = getattr(
        settings,
        "SECURITY_ALERT_EMAIL_SENDER",
        getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@example.com"),
    )

    send_mail(subject, body, from_email, list(recipients), fail_silently=True)


@dataclass
class AlertMessage:
    """Structured information describing a security alert."""

    title: str
    body: str
    severity: str = "critical"
    metadata: Mapping[str, object] | None = None

    def build_slack_payload(self) -> dict[str, object]:
        """Return a Slack compatible payload for the alert."""

        attachments: list[dict[str, object]] = []
        if self.metadata:
            fields = [
                {"title": str(key).title(), "value": str(value), "short": True}
                for key, value in self.metadata.items()
            ]
            if fields:
                attachments.append({"fields": fields})

        return {
            "text": f"[{self.severity.upper()}] {self.title}",
            "attachments": attachments,
        }

    def build_email_subject(self) -> str:
        """Return an email subject prefixed with the severity level."""

        prefix = getattr(settings, "SECURITY_ALERT_EMAIL_SUBJECT_PREFIX", "Security")
        return f"[{prefix}][{self.severity.upper()}] {self.title}"


def _build_email_body(alert: AlertMessage) -> str:
    """Return the email body including optional metadata."""

    if not alert.metadata:
        return alert.body

    details = ["", "Details:"]
    for key, value in sorted(alert.metadata.items()):
        details.append(f"- {key}: {value}")

    return "\n".join([alert.body, *details])


def send_security_alert(alert: AlertMessage) -> None:
    """Dispatch a security alert via the configured notification channels."""

    LOGGER.info(
        "Dispatching security alert", extra={"severity": alert.severity, "title": alert.title}
    )

    _send_slack_notification(alert.build_slack_payload())
    _send_email_notification(alert.build_email_subject(), _build_email_body(alert))


__all__ = ["AlertMessage", "send_security_alert"]

