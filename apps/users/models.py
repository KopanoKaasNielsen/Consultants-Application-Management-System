"""Model definitions for the users app."""

from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    """Record of sensitive staff or administrator actions."""

    class ActionType(models.TextChoices):
        VIEW_CONSULTANT = "view_consultant", "Viewed consultant"
        EXPORT_PDF = "export_pdf", "Exported consultant PDF"
        EXPORT_BULK_PDF = "export_bulk_pdf", "Exported bulk consultant PDF"
        EXPORT_CSV = "export_csv", "Exported consultant CSV"
        APPROVE_APPLICATION = "approve_application", "Approved application"
        REJECT_APPLICATION = "reject_application", "Rejected application"
        REQUEST_INFO = "request_info", "Requested more information"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="audit_logs",
    )
    action_type = models.CharField(max_length=64, choices=ActionType.choices)
    target_object = models.CharField(max_length=255, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    metadata = models.JSONField(blank=True, default=dict)

    class Meta:
        ordering = ("-timestamp", "-id")

    def __str__(self) -> str:  # pragma: no cover - human readable representation
        return f"{self.timestamp:%Y-%m-%d %H:%M:%S} - {self.user} - {self.action_type}"

