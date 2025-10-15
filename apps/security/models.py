"""Models supporting application security controls."""

from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    """Record of security-sensitive events triggered by users or systems."""

    class ActionCode(models.TextChoices):
        VIEW_CONSULTANT = "view_consultant", "Viewed consultant"
        EXPORT_PDF = "export_pdf", "Exported consultant PDF"
        EXPORT_BULK_PDF = "export_bulk_pdf", "Exported bulk consultant PDF"
        EXPORT_CSV = "export_csv", "Exported consultant CSV"
        APPROVE_APPLICATION = "approve_application", "Approved application"
        REJECT_APPLICATION = "reject_application", "Rejected application"
        REQUEST_INFO = "request_info", "Requested more information"
        SEND_ANALYTICS_REPORT = "send_analytics_report", "Sent analytics report"
        CERTIFICATE_ISSUED = "certificate_issued", "Issued consultant certificate"
        CERTIFICATE_REVOKED = "certificate_revoked", "Revoked consultant certificate"
        LOGIN_SUCCESS = "login_success", "Successful login"
        LOGIN_FAILURE = "login_failure", "Failed login"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="security_audit_logs",
        null=True,
        blank=True,
    )
    resolved_role = models.CharField(max_length=32, blank=True)
    action_code = models.CharField(max_length=64, choices=ActionCode.choices)
    target = models.CharField(max_length=255, blank=True)
    endpoint = models.CharField(max_length=255, blank=True)
    client_ip = models.GenericIPAddressField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    context = models.JSONField(blank=True, default=dict)

    class Meta:
        ordering = ("-timestamp", "-id")

    def __str__(self) -> str:  # pragma: no cover - human readable representation
        identifier = self.user or "anonymous"
        return f"{self.timestamp:%Y-%m-%d %H:%M:%S} - {identifier} - {self.action_code}"
