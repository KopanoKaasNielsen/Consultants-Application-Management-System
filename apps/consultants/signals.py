"""Signal handlers for consultant related events."""

from __future__ import annotations

import logging
from typing import Dict, List

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models import Count, Q
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse

from apps.consultants.models import Consultant

logger = logging.getLogger(__name__)


def _build_recent_applications() -> List[Dict[str, object]]:
    recent_consultants = (
        Consultant.objects.exclude(submitted_at__isnull=True)
        .select_related("user")
        .order_by("-updated_at", "-id")[:5]
    )

    recent_payload: List[Dict[str, object]] = []
    for application in recent_consultants:
        recent_payload.append(
            {
                "id": application.pk,
                "full_name": application.full_name,
                "status": application.get_status_display(),
                "submitted_at": application.submitted_at.isoformat()
                if application.submitted_at
                else None,
                "updated_at": application.updated_at.isoformat()
                if application.updated_at
                else None,
                "detail_url": reverse("staff_consultant_detail", args=[application.pk]),
            }
        )
    return recent_payload


def _build_status_counts() -> Dict[str, int]:
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


@receiver(post_save, sender=Consultant)
def broadcast_new_consultant_submission(sender, instance: Consultant, created: bool, **kwargs):
    """Broadcast a websocket event when a consultant application is created."""

    if not created:
        return

    channel_layer = get_channel_layer()
    if channel_layer is None:
        logger.debug("No channel layer configured; skipping staff broadcast for consultant %s", instance.pk)
        return

    try:
        async_to_sync(channel_layer.group_send)(
            "staff_consultant_notifications",
            {
                "type": "staff_consultant_created",
                "payload": {
                    "consultant": {
                        "id": instance.pk,
                        "full_name": instance.full_name,
                        "status": instance.status,
                        "detail_url": reverse("staff_consultant_detail", args=[instance.pk]),
                        "submitted_at": instance.submitted_at.isoformat()
                        if instance.submitted_at
                        else None,
                        "updated_at": instance.updated_at.isoformat()
                        if instance.updated_at
                        else None,
                    },
                    "unseen_count": Consultant.objects.filter(is_seen_by_staff=False).count(),
                    "status_counts": _build_status_counts(),
                    "recent_applications": _build_recent_applications(),
                },
            },
        )
    except Exception:  # pragma: no cover - defensive logging
        logger.exception("Failed to broadcast staff consultant notification event")
