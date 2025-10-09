"""Context processors for consultant-facing features."""

from typing import Dict, List

from django.http import HttpRequest

from apps.consultants.models import Notification
from apps.users.constants import UserRole as Roles
from apps.users.permissions import user_has_role


def consultant_notifications(request: HttpRequest) -> Dict[str, object]:
    """Expose recent consultant notifications to templates."""

    user = getattr(request, "user", None)
    if not getattr(user, "is_authenticated", False):
        return {
            "consultant_notifications": [],
            "unread_notification_count": 0,
            "show_consultant_notifications": False,
        }

    if not user_has_role(user, Roles.CONSULTANT):
        return {
            "consultant_notifications": [],
            "unread_notification_count": 0,
            "show_consultant_notifications": False,
        }

    notifications: List[Notification] = list(
        Notification.objects.filter(recipient=user)
        .order_by("-created_at")[:10]
    )

    unread_count = sum(1 for notification in notifications if not notification.is_read)

    return {
        "consultant_notifications": notifications,
        "unread_notification_count": unread_count,
        "show_consultant_notifications": True,
    }
