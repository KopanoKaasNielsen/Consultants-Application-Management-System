"""Shared analytics utilities for consultant reporting."""
from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional

from django.db.models import Count, Q, QuerySet
from django.db.models.functions import Coalesce, TruncMonth

from apps.consultants.models import Consultant

ANALYTICS_PENDING_STATUSES = {"submitted", "incomplete", "vetted"}


def _build_analytics_queryset(
    start_date: Optional[date],
    end_date: Optional[date],
    consultant_type: Optional[str],
) -> QuerySet[Consultant]:
    """Return a consultant queryset filtered for analytics reporting."""

    queryset = Consultant.objects.annotate(
        activity_date=Coalesce("submitted_at", "updated_at")
    )

    if start_date:
        queryset = queryset.filter(activity_date__date__gte=start_date)

    if end_date:
        queryset = queryset.filter(activity_date__date__lte=end_date)

    if consultant_type:
        queryset = queryset.filter(consultant_type=consultant_type)

    return queryset


def _serialise_monthly_trends(queryset: QuerySet[Consultant]) -> List[Dict[str, object]]:
    """Return aggregated monthly analytics suitable for charting."""

    monthly_queryset = (
        queryset.annotate(month=TruncMonth("activity_date"))
        .values("month")
        .annotate(
            total=Count("id"),
            approved=Count("id", filter=Q(status="approved")),
            rejected=Count("id", filter=Q(status="rejected")),
            pending=Count("id", filter=Q(status__in=ANALYTICS_PENDING_STATUSES)),
        )
        .order_by("month")
    )

    trends: List[Dict[str, object]] = []
    for entry in monthly_queryset:
        month = entry.get("month")
        if month is None:
            continue

        trends.append(
            {
                "month": month.date().isoformat(),
                "label": month.strftime("%b %Y"),
                "total": entry.get("total", 0),
                "approved": entry.get("approved", 0),
                "rejected": entry.get("rejected", 0),
                "pending": entry.get("pending", 0),
            }
        )

    return trends


def _serialise_type_breakdown(queryset: QuerySet[Consultant]) -> List[Dict[str, object]]:
    """Return aggregated analytics grouped by consultant type."""

    type_queryset = (
        queryset.values("consultant_type")
        .annotate(total=Count("id"))
        .order_by("consultant_type")
    )

    breakdown: List[Dict[str, object]] = []
    for entry in type_queryset:
        label = entry.get("consultant_type") or "Unspecified"
        breakdown.append({"label": label, "total": entry.get("total", 0)})

    return breakdown


__all__ = [
    "ANALYTICS_PENDING_STATUSES",
    "_build_analytics_queryset",
    "_serialise_monthly_trends",
    "_serialise_type_breakdown",
]
