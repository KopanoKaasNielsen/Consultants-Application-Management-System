"""Utilities for building and emailing consultant analytics reports."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMessage
from django.db.models import Count, Q
from django.template.loader import render_to_string
from django.utils import timezone
from weasyprint import HTML

from apps.users.analytics import (
    ANALYTICS_PENDING_STATUSES,
    _build_analytics_queryset,
    _serialise_monthly_trends,
    _serialise_type_breakdown,
)
from apps.users.constants import UserRole, groups_for_roles

logger = logging.getLogger(__name__)


@dataclass
class AnalyticsReport:
    """Representation of a rendered analytics report."""

    context: Dict[str, object]
    pdf_bytes: bytes
    filename: str


def build_report_context(
    *,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    consultant_type: Optional[str] = None,
    generated_at: Optional[datetime] = None,
) -> Dict[str, object]:
    """Return context suitable for the analytics export template."""

    queryset = _build_analytics_queryset(start_date, end_date, consultant_type)
    metrics = queryset.aggregate(
        total_applications=Count("id"),
        approved=Count("id", filter=Q(status="approved")),
        rejected=Count("id", filter=Q(status="rejected")),
        pending=Count("id", filter=Q(status__in=ANALYTICS_PENDING_STATUSES)),
    )

    timestamp = timezone.localtime(generated_at) if generated_at else timezone.localtime()

    return {
        "generated_at": timestamp,
        "metrics": {
            "total_applications": metrics.get("total_applications", 0),
            "approved": metrics.get("approved", 0),
            "rejected": metrics.get("rejected", 0),
            "pending": metrics.get("pending", 0),
        },
        "monthly_trends": _serialise_monthly_trends(queryset),
        "type_breakdown": _serialise_type_breakdown(queryset),
        "filters": {
            "start": start_date,
            "end": end_date,
            "consultant_type": consultant_type,
        },
    }


def render_report_pdf(
    context: Dict[str, object], *, base_url: Optional[str] = None
) -> AnalyticsReport:
    """Render the analytics report to PDF bytes."""

    html_string = render_to_string("staff_analytics_export_pdf.html", context)
    resolved_base_url = base_url or str(getattr(settings, "BASE_DIR", "."))
    pdf_bytes = HTML(string=html_string, base_url=resolved_base_url).write_pdf()

    generated_at = context["generated_at"]
    filename = f"consultant-analytics-{generated_at.strftime('%Y%m%d%H%M%S')}.pdf"

    return AnalyticsReport(context=context, pdf_bytes=pdf_bytes, filename=filename)


def generate_analytics_report(
    *,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    consultant_type: Optional[str] = None,
    generated_at: Optional[datetime] = None,
    base_url: Optional[str] = None,
) -> AnalyticsReport:
    """Build and render the analytics report."""

    context = build_report_context(
        start_date=start_date,
        end_date=end_date,
        consultant_type=consultant_type,
        generated_at=generated_at,
    )
    return render_report_pdf(context, base_url=base_url)


def _collect_recipient_emails() -> List[str]:
    """Return the set of active staff and admin email addresses."""

    staff_groups = groups_for_roles([UserRole.STAFF, UserRole.ADMIN])
    user_model = get_user_model()

    queryset = user_model.objects.filter(is_active=True).filter(
        Q(is_superuser=True) | Q(groups__name__in=staff_groups)
    )
    queryset = queryset.exclude(email__isnull=True).exclude(email__exact="")

    return list(queryset.values_list("email", flat=True).distinct())


def _build_weekly_email_body(start_date: date, end_date: date) -> str:
    """Return the plain-text body for the weekly analytics email."""

    return (
        "Hello,\n\n"
        "Please find attached the consultant analytics report covering "
        f"{start_date:%d %b %Y} to {end_date:%d %b %Y}.\n\n"
        "Regards,\nConsultant Application Management System"
    )


def send_weekly_analytics_report(
    *,
    current_time: Optional[datetime] = None,
    base_url: Optional[str] = None,
) -> bool:
    """Generate and send the weekly consultant analytics email."""

    timestamp = timezone.localtime(current_time) if current_time else timezone.localtime()
    end_date = timestamp.date() - timedelta(days=1)
    start_date = end_date - timedelta(days=6)

    recipients = _collect_recipient_emails()
    if not recipients:
        logger.warning("No recipients found for weekly analytics report; skipping send.")
        return False

    report = generate_analytics_report(
        start_date=start_date,
        end_date=end_date,
        generated_at=timestamp,
        base_url=base_url,
    )

    subject = "Weekly Consultant Analytics Report"
    body = _build_weekly_email_body(start_date, end_date)
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "webmaster@localhost")

    message = EmailMessage(subject, body, from_email, recipients)
    message.attach(report.filename, report.pdf_bytes, "application/pdf")

    try:
        message.send(fail_silently=False)
    except Exception:  # pragma: no cover - ensures logging for unexpected failure
        logger.exception("Failed to deliver weekly consultant analytics report email.")
        raise

    logger.info(
        "Weekly consultant analytics report sent to %s recipients covering %s - %s.",
        len(recipients),
        start_date.isoformat(),
        end_date.isoformat(),
    )
    return True


__all__ = [
    "AnalyticsReport",
    "build_report_context",
    "generate_analytics_report",
    "render_report_pdf",
    "send_weekly_analytics_report",
]
