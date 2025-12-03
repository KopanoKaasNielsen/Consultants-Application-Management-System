"""Signal handlers for consultant related events."""

from __future__ import annotations

import logging
from typing import Dict, List

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse

from apps.consultants.models import Consultant
from apps.consultants.services.dashboard import (
    build_recent_applications,
    build_status_counts,
)

logger = logging.getLogger(__name__)


def _build_recent_applications() -> List[Dict[str, object]]:
    return build_recent_applications()


def _build_status_counts() -> Dict[str, int]:
    return build_status_counts()


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
