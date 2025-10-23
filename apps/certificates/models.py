import uuid

from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

from apps.consultants.models import Consultant


class CertificateRenewal(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        DENIED = "denied", "Denied"

    consultant = models.ForeignKey(
        Consultant,
        on_delete=models.CASCADE,
        related_name="certificate_renewals",
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    processed_at = models.DateTimeField(blank=True, null=True)
    processed_by = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-requested_at"]

    def __str__(self) -> str:  # pragma: no cover - human-readable representation
        return (
            f"Renewal for {self.consultant.full_name} "
            f"({self.get_status_display()})"
        )


User = get_user_model()


class Certificate(models.Model):
    consultant = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="certificates",
    )
    certificate_number = models.CharField(
        max_length=64,
        unique=True,
        default=uuid.uuid4,
    )
    issued_on = models.DateField(default=timezone.now)
    valid_until = models.DateField()
    remarks = models.TextField(blank=True, null=True)
    quick_issue = models.BooleanField(default=False)

    def __str__(self) -> str:  # pragma: no cover - human-readable representation
        return f"Certificate {self.certificate_number} - {self.consultant.username}"
