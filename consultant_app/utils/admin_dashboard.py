"""Utilities for aggregating analytics powering the admin dashboard."""

from __future__ import annotations

from datetime import date
from typing import Dict, List

from django.db.models import Count, Q
from django.db.models.functions import TruncMonth

from apps.consultants.models import Consultant as Application
from consultant_app.models import Certificate

PENDING_STATUSES = {"submitted", "incomplete", "vetted"}


def _serialise_month(value) -> str:
    """Return an ISO formatted ``YYYY-MM`` string for the given month value."""

    if value is None:
        return ""
    if isinstance(value, date):
        return value.replace(day=1).isoformat()
    return value.strftime("%Y-%m-01")


def compute_admin_dashboard_stats() -> Dict[str, object]:
    """Return aggregated metrics for the admin dashboard analytics widgets."""

    applications = Application.objects.exclude(status="draft")

    status_counts = applications.aggregate(
        approved=Count("id", filter=Q(status="approved")),
        pending=Count("id", filter=Q(status__in=PENDING_STATUSES)),
        rejected=Count("id", filter=Q(status="rejected")),
    )

    revoked_certificates = Certificate.objects.filter(
        status=Certificate.Status.REVOKED
    ).count()

    monthly_submissions = (
        applications.exclude(submitted_at__isnull=True)
        .annotate(month=TruncMonth("submitted_at"))
        .values("month")
        .annotate(total=Count("id"))
        .order_by("month")
    )

    certificate_distribution = (
        Certificate.objects.values("status")
        .annotate(total=Count("id"))
        .order_by("status")
    )

    def _format_certificate(entry: Dict[str, object]) -> Dict[str, object]:
        status = entry["status"]
        label = status
        try:
            label = Certificate.Status(status).label  # type: ignore[arg-type]
        except ValueError:
            label = str(status)
        return {
            "status": str(status),
            "label": label,
            "count": int(entry["total"] or 0),
        }

    monthly_trend: List[Dict[str, object]] = [
        {
            "month": _serialise_month(entry["month"]),
            "total": int(entry["total"] or 0),
        }
        for entry in monthly_submissions
    ]

    certificate_statuses: List[Dict[str, object]] = [
        _format_certificate(entry) for entry in certificate_distribution
    ]

    return {
        "total_applications": applications.count(),
        "status_breakdown": {
            "approved": int(status_counts.get("approved") or 0),
            "pending": int(status_counts.get("pending") or 0),
            "rejected": int(status_counts.get("rejected") or 0),
            "revoked": int(revoked_certificates),
        },
        "monthly_trends": monthly_trend,
        "certificate_statuses": certificate_statuses,
    }


__all__ = ["compute_admin_dashboard_stats"]
