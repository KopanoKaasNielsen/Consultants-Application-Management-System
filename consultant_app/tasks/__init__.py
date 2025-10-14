"""Celery tasks for the simplified consultant application."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from celery import Celery, shared_task
from celery.utils.log import get_task_logger
from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from consultant_app import settings as consultant_settings

celery_app = Celery("consultant_app")
celery_app.config_from_object("django.conf:settings", namespace="CELERY")
celery_app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)
celery_app.conf.update(
    task_default_queue=consultant_settings.CELERY_TASK_DEFAULT_QUEUE,
    task_default_exchange=consultant_settings.CELERY_TASK_DEFAULT_EXCHANGE,
    task_default_routing_key=consultant_settings.CELERY_TASK_DEFAULT_ROUTING_KEY,
)
celery_app.set_default()

logger = get_task_logger(__name__)


@dataclass(frozen=True)
class _TaskContext:
    """Structured metadata describing the asynchronous execution."""

    source: str
    task_id: str | None
    task_name: str
    extra: Mapping[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        payload = {
            "source": self.source,
            "task_id": self.task_id,
            "task_name": self.task_name,
        }
        if self.extra:
            payload.update(dict(self.extra))
        return payload


def _resolve_consultant(identifier: Any):
    """Resolve a consultant either by primary key or email address."""

    from apps.consultants.models import Consultant

    queryset = Consultant.objects.select_related("user")

    if isinstance(identifier, int):
        return queryset.get(pk=identifier)

    if isinstance(identifier, str):
        candidate = identifier.strip()
        if candidate.isdigit():
            return queryset.get(pk=int(candidate))
        if "@" in candidate:
            try:
                return queryset.get(email__iexact=candidate)
            except Consultant.DoesNotExist:
                return queryset.get(user__email__iexact=candidate)

    raise Consultant.DoesNotExist  # type: ignore[misc]


def _resolve_actor(actor_id: int | None):
    """Return the user instance backing the provided identifier."""

    if not actor_id:
        return None

    UserModel = get_user_model()
    return UserModel.objects.filter(pk=actor_id).first()


def _actor_display(actor) -> str | None:
    """Return a human readable label for the acting user."""

    if actor is None:
        return None

    full_name_getter = getattr(actor, "get_full_name", None)
    if callable(full_name_getter):
        full_name = full_name_getter()
        if full_name:
            return full_name

    username = getattr(actor, "username", None)
    if username:
        return username

    email = getattr(actor, "email", None)
    if email:
        return email

    return None


def _notify_consultant(consultant, message: str, *, context: dict[str, Any]) -> None:
    """Persist an in-app notification for the consultant."""

    Notification = apps.get_model("consultants", "Notification")
    if not consultant.user_id:
        logger.debug(
            "Skipping notification dispatch because consultant has no user account.",
            extra={
                "consultant_id": consultant.pk,
                "context": context,
            },
        )
        return

    notification = Notification.objects.create(
        recipient=consultant.user,
        notification_type=Notification.NotificationType.COMMENT,
        message=message,
    )

    logger.info(
        "Notification %s dispatched for consultant %s",
        notification.pk,
        consultant.pk,
        extra={
            "consultant_id": consultant.pk,
            "notification_id": notification.pk,
            "context": context,
        },
    )


@shared_task(
    bind=True,
    name="consultant_app.send_confirmation_email",
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=5,
    retry_jitter=True,
    retry_kwargs={"max_retries": 3},
)
def send_confirmation_email(self, consultant_identifier: Any) -> None:
    """Send the consultant submission confirmation email."""

    from apps.consultants.emails import send_submission_confirmation_email
    from apps.consultants.models import Consultant

    try:
        consultant = _resolve_consultant(consultant_identifier)
    except Consultant.DoesNotExist:
        logger.warning(
            "Consultant %s could not be found for confirmation email.",
            consultant_identifier,
            extra={
                "context": {
                    "action": "consultant_app.confirmation_email.missing",
                    "identifier": consultant_identifier,
                },
            },
        )
        return None

    logger.info(
        "Dispatching confirmation email for consultant %s",
        consultant.pk,
        extra={
            "consultant_id": consultant.pk,
            "user_id": consultant.user_id,
            "context": {
                "action": "consultant_app.confirmation_email.dispatch",
                "consultant_id": consultant.pk,
                "user_id": consultant.user_id,
            },
        },
    )

    try:
        send_submission_confirmation_email(consultant)
    except Exception:  # pragma: no cover - ensures retries log context
        logger.exception(
            "Failed to send confirmation email for consultant %s",
            consultant.pk,
            extra={
                "consultant_id": consultant.pk,
                "user_id": consultant.user_id,
                "context": {
                    "action": "consultant_app.confirmation_email.error",
                    "consultant_id": consultant.pk,
                    "user_id": consultant.user_id,
                },
            },
        )
        raise

    logger.info(
        "Sent confirmation email for consultant %s",
        consultant.pk,
        extra={
            "consultant_id": consultant.pk,
            "user_id": consultant.user_id,
            "context": {
                "action": "consultant_app.confirmation_email.sent",
                "consultant_id": consultant.pk,
                "user_id": consultant.user_id,
            },
        },
    )


@shared_task(
    bind=True,
    name="consultant_app.certificate_revoke",
    autoretry_for=(TimeoutError,),
    retry_backoff=5,
    retry_jitter=True,
    retry_kwargs={"max_retries": 5},
)
def revoke_certificate_task(
    self,
    consultant_identifier: Any,
    *,
    reason: str,
    actor_id: int | None = None,
    notify_consultant: bool = True,
    metadata: Mapping[str, Any] | None = None,
) -> None:
    """Revoke the consultant's active certificate and notify stakeholders."""

    from apps.consultants.models import Consultant

    try:
        consultant = _resolve_consultant(consultant_identifier)
    except Consultant.DoesNotExist:
        logger.warning(
            "Unable to revoke certificate for missing consultant %s",
            consultant_identifier,
            extra={
                "context": {
                    "action": "certificate.revoke.missing_consultant",
                    "consultant_identifier": consultant_identifier,
                    "task_id": getattr(self.request, "id", None),
                },
            },
        )
        return

    actor = _resolve_actor(actor_id)
    task_context = _TaskContext(
        source="celery",
        task_id=getattr(self.request, "id", None),
        task_name=self.name,
        extra=metadata,
    ).as_dict()

    from consultant_app.certificates import update_certificate_status
    CertificateModel = apps.get_model("consultant_app", "Certificate")

    with transaction.atomic():
        certificate = update_certificate_status(
            consultant,
            status=CertificateModel.Status.REVOKED,
            user=actor,
            reason=reason,
            timestamp=timezone.now(),
            context=task_context,
        )

        if certificate is None:
            logger.warning(
                "No certificate to revoke for consultant %s",
                consultant.pk,
                extra={
                    "consultant_id": consultant.pk,
                    "user_id": getattr(actor, "pk", None),
                    "context": {
                        **task_context,
                        "action": "certificate.revoke.missing_certificate",
                    },
                },
            )
            return

        if notify_consultant:
            message = (
                "Your consultant certificate has been revoked."
                + (f" Reason: {reason}" if reason else "")
            )
            _notify_consultant(
                consultant,
                message,
                context={
                    **task_context,
                    "action": "certificate.revoke.notification",
                    "certificate_id": certificate.pk,
                },
            )
            from .notifications import send_certificate_notification

            send_certificate_notification.delay(
                consultant.pk,
                event="revoked",
                certificate_id=certificate.pk,
                reason=reason,
                actor_id=getattr(actor, "pk", None),
                metadata={
                    **task_context,
                    "action": "certificate.revoke.notification",
                },
            )

        logger.info(
            "Certificate %s for consultant %s revoked via task",
            certificate.pk,
            consultant.pk,
            extra={
                "consultant_id": consultant.pk,
                "certificate_id": certificate.pk,
                "user_id": getattr(actor, "pk", None),
                "context": {
                    **task_context,
                    "action": "certificate.revoke.completed",
                    "certificate_id": certificate.pk,
                },
            },
        )


@shared_task(
    bind=True,
    name="consultant_app.certificate_reissue",
    autoretry_for=(TimeoutError,),
    retry_backoff=5,
    retry_jitter=True,
    retry_kwargs={"max_retries": 5},
)
def reissue_certificate_task(
    self,
    consultant_identifier: Any,
    *,
    reason: str,
    actor_id: int | None = None,
    notify_consultant: bool = True,
    metadata: Mapping[str, Any] | None = None,
) -> None:
    """Reissue an approval certificate, replacing the active signed token."""

    from apps.consultants.models import Consultant

    try:
        consultant = _resolve_consultant(consultant_identifier)
    except Consultant.DoesNotExist:
        logger.warning(
            "Unable to reissue certificate for missing consultant %s",
            consultant_identifier,
            extra={
                "context": {
                    "action": "certificate.reissue.missing_consultant",
                    "consultant_identifier": consultant_identifier,
                    "task_id": getattr(self.request, "id", None),
                },
            },
        )
        return

    actor = _resolve_actor(actor_id)
    task_context = _TaskContext(
        source="celery",
        task_id=getattr(self.request, "id", None),
        task_name=self.name,
        extra=metadata,
    ).as_dict()

    from consultant_app.certificates import (
        build_verification_url,
        render_certificate_pdf,
        update_certificate_status,
    )
    CertificateModel = apps.get_model("consultant_app", "Certificate")

    with transaction.atomic():
        transition_time = timezone.now()
        current_certificate = update_certificate_status(
            consultant,
            status=CertificateModel.Status.REISSUED,
            user=actor,
            reason=reason,
            timestamp=transition_time,
            context=task_context,
        )

        if current_certificate is None:
            logger.warning(
                "No certificate available to reissue for consultant %s",
                consultant.pk,
                extra={
                    "consultant_id": consultant.pk,
                    "user_id": getattr(actor, "pk", None),
                    "context": {
                        **task_context,
                        "action": "certificate.reissue.missing_certificate",
                    },
                },
            )
            return

        fresh_issue_timestamp = timezone.now()
        fresh_certificate = CertificateModel.objects.create(
            consultant=consultant,
            status=CertificateModel.Status.VALID,
            issued_at=fresh_issue_timestamp,
            status_set_at=fresh_issue_timestamp,
            valid_at=fresh_issue_timestamp,
            status_reason="",
        )

        consultant.certificate_generated_at = fresh_issue_timestamp

        if consultant.certificate_pdf:
            consultant.certificate_pdf.delete(save=False)

        verification_url = build_verification_url(consultant)
        issued_on = timezone.localtime(fresh_issue_timestamp).date()
        generated_by = _actor_display(actor)
        pdf_stream = render_certificate_pdf(
            consultant,
            issued_at=issued_on,
            verification_url=verification_url,
            generated_by=generated_by,
        )

        pdf_content = ContentFile(pdf_stream.getvalue())
        filename = f"approval-certificate-{consultant.pk}.pdf"
        consultant.certificate_pdf.save(filename, pdf_content, save=False)
        consultant.save(
            update_fields=["certificate_pdf", "certificate_generated_at", "updated_at"],
        )

        if notify_consultant:
            message = (
                "Your consultant certificate has been reissued with updated details."
                + (f" Reason: {reason}" if reason else "")
            )
            _notify_consultant(
                consultant,
                message,
                context={
                    **task_context,
                    "action": "certificate.reissue.notification",
                    "certificate_id": fresh_certificate.pk,
                },
            )
            from .notifications import send_certificate_notification

            send_certificate_notification.delay(
                consultant.pk,
                event="reissued",
                certificate_id=fresh_certificate.pk,
                reason=reason,
                actor_id=getattr(actor, "pk", None),
                metadata={
                    **task_context,
                    "action": "certificate.reissue.notification",
                },
            )

        logger.info(
            "Issued replacement certificate %s for consultant %s",
            fresh_certificate.pk,
            consultant.pk,
            extra={
                "consultant_id": consultant.pk,
                "certificate_id": fresh_certificate.pk,
                "previous_certificate_id": current_certificate.pk,
                "user_id": getattr(actor, "pk", None),
                "context": {
                    **task_context,
                    "action": "certificate.reissue.completed",
                    "certificate_id": fresh_certificate.pk,
                },
            },
        )


from .notifications import send_certificate_notification


__all__ = [
    "celery_app",
    "reissue_certificate_task",
    "revoke_certificate_task",
    "send_certificate_notification",
    "send_confirmation_email",
]
