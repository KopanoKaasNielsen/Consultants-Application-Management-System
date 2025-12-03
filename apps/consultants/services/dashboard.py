"""Shared helpers for staff dashboard summaries and notification payloads."""

from __future__ import annotations

from typing import List

from django.db.models import Count, Q
from django.urls import reverse

from apps.consultants.models import Consultant


def build_status_counts() -> dict[str, int]:
    """Return aggregate counts for key consultant statuses."""

    aggregates = Consultant.objects.aggregate(
        draft=Count("id", filter=Q(status="draft")),
        submitted=Count("id", filter=Q(status="submitted")),
        rejected=Count("id", filter=Q(status="rejected")),
        approved=Count("id", filter=Q(status="approved")),
    )

    return {
        "draft": aggregates.get("draft", 0) or 0,
        "submitted": aggregates.get("submitted", 0) or 0,
        "rejected": aggregates.get("rejected", 0) or 0,
        "approved": aggregates.get("approved", 0) or 0,
    }


def build_recent_applications(limit: int = 5) -> List[dict[str, str | int | None]]:
    """Return the most recent submitted applications for staff views."""

    recent = Consultant.objects.filter(status="submitted").order_by("-submitted_at")[:limit]
    payload: List[dict[str, str | int | None]] = []

    for consultant in recent:
        payload.append(
            {
                "id": consultant.pk,
                "full_name": consultant.full_name,
                "status": consultant.get_status_display(),
                "submitted_at": consultant.submitted_at.isoformat() if consultant.submitted_at else None,
                "updated_at": consultant.updated_at.isoformat() if consultant.updated_at else None,
                "detail_url": reverse("staff_consultant_detail", args=[consultant.pk]),
            }
        )

    return payload
