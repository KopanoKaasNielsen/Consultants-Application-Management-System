"""Scheduled tasks for delivering admin analytics reports."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable
from urllib.parse import urljoin

from celery import shared_task
from celery.utils.log import get_task_logger
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives
from django.db.models import Q
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import strip_tags

from apps.users.constants import ADMINS_GROUP_NAME, UserRole, groups_for_roles
from consultant_app.utils.report_exporter import (
    describe_filters,
    prepare_dashboard_rows,
    render_dashboard_pdf,
    summarise_rows,
)
from consultant_app.views import build_dashboard_queryset

logger = get_task_logger(__name__)

_FREQUENCY_LABELS = {
    "weekly": "Weekly",
    "monthly": "Monthly",
    "manual": "Manual",
}


@dataclass(frozen=True)
class ReportPayload:
    """Snapshot of the generated dashboard report."""

    pdf_bytes: bytes
    summary: dict[str, Any]
    filters: list[dict[str, str]]
    generated_at: datetime
    total_rows: int


def _actor_display(actor) -> str | None:
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


def _report_base_url() -> str:
    base_url = getattr(settings, "ADMIN_REPORT_BASE_URL", "http://localhost:8000/")
    if not base_url.endswith("/"):
        base_url = f"{base_url}/"
    return base_url


def _dashboard_url() -> str:
    base_url = _report_base_url()
    return urljoin(base_url, "admin-dashboard/")


def _resolve_recipients() -> list[str]:
    configured = getattr(settings, "ADMIN_REPORT_RECIPIENTS", ()) or ()
    if configured:
        return [email for email in configured if email]

    UserModel = get_user_model()
    admin_groups = groups_for_roles([UserRole.BOARD]) | {ADMINS_GROUP_NAME}
    candidates = (
        UserModel.objects.filter(is_active=True)
        .filter(Q(is_superuser=True) | Q(groups__name__in=admin_groups))
        .values_list("email", flat=True)
        .distinct()
    )
    recipients = [email for email in candidates if email]
    return sorted(set(recipients))


def _build_report_payload() -> ReportPayload:
    queryset, filters = build_dashboard_queryset({})
    queryset = queryset.select_related("user").prefetch_related("certificate_records")
    consultants = list(queryset)
    rows = prepare_dashboard_rows(consultants)
    summary = summarise_rows(rows)
    filter_descriptions = describe_filters(filters)
    generated_at = timezone.localtime(timezone.now())

    pdf_bytes = render_dashboard_pdf(
        rows=rows,
        filters=filter_descriptions,
        summary=summary,
        generated_at=generated_at,
        base_url=_report_base_url(),
    )

    return ReportPayload(
        pdf_bytes=pdf_bytes,
        summary=summary,
        filters=filter_descriptions,
        generated_at=generated_at,
        total_rows=len(rows),
    )


def _resolve_subject(frequency: str, generated_at) -> str:
    subjects = getattr(settings, "ADMIN_REPORT_SUBJECTS", {})
    base_subject = subjects.get(frequency, "Consultant analytics report")
    return f"{base_subject} – {generated_at:%d %b %Y}"


def _attachment_name(frequency: str, generated_at) -> str:
    prefix = getattr(settings, "ADMIN_REPORT_ATTACHMENT_PREFIX", "consultant-analytics")
    timestamp = generated_at.strftime("%Y%m%d-%H%M%S")
    return f"{prefix}-{frequency}-{timestamp}.pdf"


def _render_email_body(
    *,
    payload: ReportPayload,
    frequency: str,
    recipients: Iterable[str],
    actor_label: str | None,
) -> tuple[str, str]:
    context = {
        "frequency": frequency,
        "frequency_label": _FREQUENCY_LABELS.get(frequency, frequency.title()),
        "generated_at": payload.generated_at,
        "summary": payload.summary,
        "filters": payload.filters,
        "total_rows": payload.total_rows,
        "dashboard_url": _dashboard_url(),
        "recipients": list(recipients),
        "triggered_by": actor_label,
    }
    html_body = render_to_string("emails/report_summary.html", context)
    plain_body = strip_tags(html_body)
    return html_body, plain_body


def _send_email(
    *,
    subject: str,
    html_body: str,
    plain_body: str,
    recipients: list[str],
    attachment_name: str,
    attachment_bytes: bytes,
) -> None:
    message = EmailMultiAlternatives(
        subject,
        plain_body,
        getattr(settings, "ADMIN_REPORT_FROM_EMAIL", None),
        recipients,
    )
    message.attach_alternative(html_body, "text/html")
    message.attach(attachment_name, attachment_bytes, "application/pdf")
    message.send()


def _send_admin_report(*, frequency: str, source: str, actor=None) -> dict[str, Any]:
    recipients = _resolve_recipients()
    actor_label = _actor_display(actor)

    if not recipients:
        logger.info(
            "Skipping analytics report dispatch because no recipients are configured.",
            extra={"frequency": frequency, "source": source, "status": "skipped"},
        )
        return {
            "status": "skipped",
            "frequency": frequency,
            "recipients": [],
            "summary": {},
            "generated_at": None,
        }

    payload = _build_report_payload()
    subject = _resolve_subject(frequency, payload.generated_at)
    attachment_name = _attachment_name(frequency, payload.generated_at)
    html_body, plain_body = _render_email_body(
        payload=payload,
        frequency=frequency,
        recipients=recipients,
        actor_label=actor_label,
    )

    _send_email(
        subject=subject,
        html_body=html_body,
        plain_body=plain_body,
        recipients=recipients,
        attachment_name=attachment_name,
        attachment_bytes=payload.pdf_bytes,
    )

    logger.info(
        "Admin analytics report dispatched.",
        extra={
            "frequency": frequency,
            "source": source,
            "recipient_count": len(recipients),
            "generated_at": payload.generated_at.isoformat(),
            "total_rows": payload.total_rows,
        },
    )

    return {
        "status": "sent",
        "frequency": frequency,
        "recipients": recipients,
        "summary": payload.summary,
        "filters": payload.filters,
        "generated_at": payload.generated_at,
        "attachment_name": attachment_name,
    }


def send_admin_report(frequency: str, *, actor=None) -> dict[str, Any]:
    """Generate and email the consultant analytics report immediately."""

    return _send_admin_report(frequency=frequency, source="manual", actor=actor)


@shared_task(name="consultant_app.send_weekly_admin_report")
def send_weekly_admin_report() -> dict[str, Any]:
    """Celery task delivering the weekly analytics report."""

    return _send_admin_report(frequency="weekly", source="schedule.weekly")


@shared_task(name="consultant_app.send_monthly_admin_report")
def send_monthly_admin_report() -> dict[str, Any]:
    """Celery task delivering the monthly analytics report."""

    return _send_admin_report(frequency="monthly", source="schedule.monthly")
