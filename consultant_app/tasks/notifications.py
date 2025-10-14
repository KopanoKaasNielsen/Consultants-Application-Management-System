"""Celery tasks for delivering certificate lifecycle notifications."""
from __future__ import annotations

import base64
import json
import logging
from typing import Any, Mapping
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from celery import shared_task
from django.apps import apps
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from consultant_app.certificates import build_verification_url
from consultant_app.signals import certificate_notification_dispatched

logger = logging.getLogger(__name__)

DEFAULT_TEMPLATES: dict[str, dict[str, str]] = {
    "issued": {
        "email_subject": "Your consultant certificate has been issued",
        "email_body": (
            "Hello {consultant_name},\n\n"
            "We are pleased to let you know that your consultant certificate"
            " {certificate_reference} was issued on {issued_on}.\n"
            "You can download the certificate from your dashboard or verify it"
            " online using {verification_url}.\n\n"
            "Regards,\nConsultant Applications Team"
        ),
        "sms_body": (
            "Your consultant certificate {certificate_reference} was issued on {issued_on}."
            " Access it from your dashboard."
        ),
    },
    "revoked": {
        "email_subject": "Important update about your consultant certificate",
        "email_body": (
            "Hello {consultant_name},\n\n"
            "Your consultant certificate {certificate_reference} was revoked on {status_on}.\n"
            "{reason_block}If you have any questions please contact our support team.\n\n"
            "Regards,\nConsultant Applications Team"
        ),
        "sms_body": (
            "Your consultant certificate {certificate_reference} was revoked."
            " {short_reason}"
        ),
    },
    "reissued": {
        "email_subject": "Your consultant certificate has been reissued",
        "email_body": (
            "Hello {consultant_name},\n\n"
            "We have reissued your consultant certificate {certificate_reference} on {issued_on}.\n"
            "Download the updated document from your dashboard or verify it online"
            " using {verification_url}.\n\n"
            "{reason_block}Regards,\nConsultant Applications Team"
        ),
        "sms_body": (
            "Your consultant certificate {certificate_reference} has been reissued."
            " Please download the updated copy."
        ),
    },
}


class NotificationDeliveryError(Exception):
    """Raised when an email notification cannot be delivered."""


class _SafeFormatDict(dict):
    """Return empty strings for missing template keys."""

    def __missing__(self, key: str) -> str:  # pragma: no cover - defensive fallback
        return ""


def _merge_templates() -> dict[str, dict[str, str]]:
    custom = getattr(settings, "CERTIFICATE_NOTIFICATION_TEMPLATES", None) or {}
    merged: dict[str, dict[str, str]] = {
        key: value.copy() for key, value in DEFAULT_TEMPLATES.items()
    }
    for event, overrides in custom.items():
        base = merged.setdefault(event, {})
        base.update({k: str(v) for k, v in overrides.items() if isinstance(v, str)})
    return merged


def _format_datetime(value) -> str:
    if not value:
        return ""
    return timezone.localtime(value).strftime("%d %B %Y")


def _build_context(
    consultant,
    certificate,
    *,
    event: str,
    reason: str,
) -> dict[str, Any]:
    issued_source = None
    if certificate and certificate.issued_at:
        issued_source = certificate.issued_at
    elif consultant.certificate_generated_at:
        issued_source = consultant.certificate_generated_at

    status_time = None
    if certificate and certificate.status_set_at:
        status_time = certificate.status_set_at

    verification_url = ""
    if event in {"issued", "reissued"}:
        try:
            verification_url = build_verification_url(consultant)
        except ValueError:
            verification_url = ""
        except Exception:  # pragma: no cover - defensive log for unexpected errors
            logger.exception(
                "Failed to build verification URL for consultant %s", consultant.pk
            )
            verification_url = ""

    reason_block = f"Reason: {reason}\n\n" if reason else ""

    context = {
        "consultant_name": consultant.full_name,
        "consultant_email": consultant.email,
        "certificate_reference": f"#{certificate.pk}" if certificate else "",
        "issued_on": _format_datetime(issued_source) if issued_source else "",
        "status_on": _format_datetime(status_time) if status_time else "",
        "verification_url": verification_url,
        "reason": reason,
        "reason_block": reason_block,
        "short_reason": reason,
        "event": event,
    }
    return context


def _notification_from_email() -> str:
    if hasattr(settings, "CERTIFICATE_NOTIFICATION_FROM_EMAIL"):
        configured = getattr(settings, "CERTIFICATE_NOTIFICATION_FROM_EMAIL")
        if configured:
            return str(configured)
    default = getattr(settings, "DEFAULT_FROM_EMAIL", None)
    return str(default or "no-reply@example.com")


def _send_email(consultant, subject_template: str, body_template: str, context: dict[str, Any]) -> bool:
    if not consultant.email:
        logger.warning(
            "Consultant %s has no email address; skipping certificate notification email.",
            consultant.pk,
            extra={"consultant_id": consultant.pk},
        )
        return False

    if not subject_template or not body_template:
        return False

    formatter = _SafeFormatDict(context)
    subject = subject_template.format_map(formatter).strip()
    body = body_template.format_map(formatter).strip()

    if not subject or not body:
        return False

    send_mail(
        subject,
        body,
        _notification_from_email(),
        [consultant.email],
        fail_silently=False,
    )
    return True


def _should_send_sms(send_sms: bool | None) -> bool:
    if send_sms is not None:
        return bool(send_sms)
    if hasattr(settings, "CERTIFICATE_NOTIFICATION_ENABLE_SMS"):
        return bool(getattr(settings, "CERTIFICATE_NOTIFICATION_ENABLE_SMS"))
    twilio_configured = all(
        getattr(settings, attr, None)
        for attr in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM_NUMBER")
    )
    gateway_configured = bool(getattr(settings, "CERTIFICATE_SMS_GATEWAY_URL", None))
    return twilio_configured or gateway_configured


def _twilio_request(account_sid: str, auth_token: str, from_number: str, to_number: str, body: str) -> None:
    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
    payload = urlencode({"To": to_number, "From": from_number, "Body": body}).encode()
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    request = Request(url, data=payload, headers=headers)
    credentials = base64.b64encode(f"{account_sid}:{auth_token}".encode()).decode()
    request.add_header("Authorization", f"Basic {credentials}")

    timeout = getattr(settings, "CERTIFICATE_NOTIFICATION_SMS_TIMEOUT", 10)
    with urlopen(request, timeout=timeout) as response:  # nosec B310
        response.read()


def _gateway_request(url: str, to_number: str, body: str) -> None:
    payload = json.dumps({"to": to_number, "message": body}).encode()
    headers = {"Content-Type": "application/json"}
    token = getattr(settings, "CERTIFICATE_SMS_GATEWAY_TOKEN", None)
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = Request(url, data=payload, headers=headers)
    timeout = getattr(settings, "CERTIFICATE_NOTIFICATION_SMS_TIMEOUT", 10)
    with urlopen(request, timeout=timeout) as response:  # nosec B310
        response.read()


def _dispatch_sms(phone_number: str, message: str) -> bool:
    account_sid = getattr(settings, "TWILIO_ACCOUNT_SID", None)
    auth_token = getattr(settings, "TWILIO_AUTH_TOKEN", None)
    from_number = getattr(settings, "TWILIO_FROM_NUMBER", None)
    if account_sid and auth_token and from_number:
        _twilio_request(account_sid, auth_token, str(from_number), phone_number, message)
        return True

    gateway_url = getattr(settings, "CERTIFICATE_SMS_GATEWAY_URL", None)
    if gateway_url:
        _gateway_request(str(gateway_url), phone_number, message)
        return True

    return False


@shared_task(
    bind=True,
    name="consultant_app.send_certificate_notification",
    autoretry_for=(NotificationDeliveryError,),
    retry_backoff=10,
    retry_jitter=True,
    retry_kwargs={"max_retries": 5},
)
def send_certificate_notification(
    self,
    consultant_id: int,
    *,
    event: str,
    certificate_id: int | None = None,
    reason: str | None = None,
    actor_id: int | None = None,
    metadata: Mapping[str, Any] | None = None,
    send_sms: bool | None = None,
) -> dict[str, Any]:
    """Send certificate lifecycle notifications to a consultant."""

    templates = _merge_templates()
    event_key = event.lower()
    if event_key not in templates:
        raise ValueError(f"Unsupported certificate notification event: {event}")
    config = templates[event_key]

    ConsultantModel = apps.get_model("consultants", "Consultant")
    CertificateModel = apps.get_model("consultant_app", "Certificate")

    try:
        consultant = ConsultantModel.objects.get(pk=consultant_id)
    except ConsultantModel.DoesNotExist:
        logger.warning(
            "Skipping certificate notification for missing consultant %s",
            consultant_id,
            extra={
                "consultant_id": consultant_id,
                "context": {
                    "action": "certificate.notification.missing_consultant",
                    "event": event_key,
                    "task_id": getattr(self.request, "id", None),
                },
            },
        )
        return {"email": "skipped", "sms": "skipped"}

    certificate = None
    if certificate_id is not None:
        certificate = CertificateModel.objects.filter(pk=certificate_id).first()
    if certificate is None:
        certificate = CertificateModel.objects.filter(
            consultant_id=consultant.pk
        ).order_by("-issued_at", "-status_set_at", "-pk").first()

    reason_text = (reason or "").strip()
    context = _build_context(consultant, certificate, event=event_key, reason=reason_text)

    task_metadata: dict[str, Any] = {
        "task_id": getattr(self.request, "id", None),
        "event": event_key,
    }
    if metadata:
        task_metadata.update(dict(metadata))
    if certificate:
        task_metadata.setdefault("certificate_id", certificate.pk)

    email_status = "skipped"
    email_error: Exception | None = None
    try:
        if not consultant.email:
            email_status = "skipped"
        elif not config.get("email_subject") or not config.get("email_body"):
            email_status = "disabled"
        else:
            delivered = _send_email(
                consultant,
                config["email_subject"],
                config["email_body"],
                context,
            )
            email_status = "sent" if delivered else "disabled"
    except Exception as exc:  # pragma: no cover - exercised via tests raising errors
        email_status = "failed"
        email_error = exc
        logger.exception(
            "Failed to send %s certificate email to consultant %s",
            event_key,
            consultant.pk,
            extra={
                "consultant_id": consultant.pk,
                "context": {
                    **task_metadata,
                    "channel": "email",
                    "reason": reason_text,
                },
            },
        )
        certificate_notification_dispatched.send(
            sender=send_certificate_notification,
            consultant_id=consultant.pk,
            event=event_key,
            channel="email",
            status=email_status,
            certificate_id=getattr(certificate, "pk", None),
            reason=reason_text,
            actor_id=actor_id,
            metadata=task_metadata,
            error=exc,
        )
        raise NotificationDeliveryError("Email delivery failed") from exc
    else:
        certificate_notification_dispatched.send(
            sender=send_certificate_notification,
            consultant_id=consultant.pk,
            event=event_key,
            channel="email",
            status=email_status,
            certificate_id=getattr(certificate, "pk", None),
            reason=reason_text,
            actor_id=actor_id,
            metadata=task_metadata,
            error=None,
        )
        if email_status == "sent":
            logger.info(
                "Sent %s certificate email notification to consultant %s",
                event_key,
                consultant.pk,
                extra={
                    "consultant_id": consultant.pk,
                    "context": {
                        **task_metadata,
                        "channel": "email",
                        "reason": reason_text,
                    },
                },
            )

    sms_status = "disabled"
    sms_error: Exception | None = None
    sms_template = config.get("sms_body", "")
    if _should_send_sms(send_sms) and sms_template:
        if consultant.phone_number:
            formatter = _SafeFormatDict(context)
            message = sms_template.format_map(formatter).strip()
            if message:
                try:
                    dispatched = _dispatch_sms(consultant.phone_number, message)
                    sms_status = "sent" if dispatched else "disabled"
                except Exception as exc:
                    sms_status = "failed"
                    sms_error = exc
                    logger.exception(
                        "Failed to send %s certificate SMS to consultant %s",
                        event_key,
                        consultant.pk,
                        extra={
                            "consultant_id": consultant.pk,
                            "context": {
                                **task_metadata,
                                "channel": "sms",
                                "reason": reason_text,
                            },
                        },
                    )
                else:
                    if sms_status == "sent":
                        logger.info(
                            "Sent %s certificate SMS notification to consultant %s",
                            event_key,
                            consultant.pk,
                            extra={
                                "consultant_id": consultant.pk,
                                "context": {
                                    **task_metadata,
                                    "channel": "sms",
                                    "reason": reason_text,
                                },
                            },
                        )
            else:
                sms_status = "disabled"
        else:
            sms_status = "skipped"
    certificate_notification_dispatched.send(
        sender=send_certificate_notification,
        consultant_id=consultant.pk,
        event=event_key,
        channel="sms",
        status=sms_status,
        certificate_id=getattr(certificate, "pk", None),
        reason=reason_text,
        actor_id=actor_id,
        metadata=task_metadata,
        error=sms_error,
    )

    return {"email": email_status, "sms": sms_status}


__all__ = ["send_certificate_notification"]
