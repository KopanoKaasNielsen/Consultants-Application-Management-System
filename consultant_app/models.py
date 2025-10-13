"""Database models and domain helpers for consultant APIs."""

from __future__ import annotations

from datetime import datetime

from django.db import models
from django.utils import timezone

from apps.consultants.models import (
    Consultant as BaseConsultant,
    LogEntry as BaseLogEntry,
)


class CertificateQuerySet(models.QuerySet):
    """Custom queryset helpers for the :class:`Certificate` model."""

    def active(self) -> "CertificateQuerySet":
        return self.filter(status__in=Certificate.ACTIVE_STATUSES)

    def for_consultant(self, consultant: BaseConsultant) -> "CertificateQuerySet":
        return self.filter(consultant=consultant)


class CertificateManager(models.Manager["Certificate"]):
    """Manager providing helpers for fetching certificate records."""

    def get_queryset(self) -> CertificateQuerySet:  # type: ignore[override]
        return CertificateQuerySet(self.model, using=self._db)

    def active_for_consultant(
        self, consultant: BaseConsultant
    ) -> "Certificate | None":
        """Return the latest active certificate for the consultant."""

        return (
            self.get_queryset()
            .for_consultant(consultant)
            .active()
            .order_by("-issued_at", "-status_set_at", "-pk")
            .first()
        )

    def latest_for_consultant(
        self, consultant: BaseConsultant
    ) -> "Certificate | None":
        """Return the most recent certificate record for the consultant."""

        return (
            self.get_queryset()
            .for_consultant(consultant)
            .order_by("-issued_at", "-status_set_at", "-pk")
            .first()
        )

    def matching_issue_timestamp(
        self, consultant: BaseConsultant, issued_at: str
    ) -> "Certificate | None":
        """Return the certificate that matches the serialized ``issued_at`` value."""

        try:
            parsed = datetime.fromisoformat(issued_at)
        except ValueError:
            return None

        return (
            self.get_queryset()
            .for_consultant(consultant)
            .filter(issued_at=parsed)
            .order_by("-pk")
            .first()
        )


class Certificate(models.Model):
    """Historical record describing the lifecycle of consultant certificates."""

    class Status(models.TextChoices):
        VALID = "valid", "Valid"
        REVOKED = "revoked", "Revoked"
        EXPIRED = "expired", "Expired"
        REISSUED = "reissued", "Reissued"

    ACTIVE_STATUSES = {Status.VALID}

    consultant = models.ForeignKey(
        BaseConsultant,
        on_delete=models.CASCADE,
        related_name="certificate_records",
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.VALID,
        db_index=True,
    )
    issued_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Timestamp when the certificate was issued.",
    )
    status_set_at = models.DateTimeField(
        default=timezone.now,
        help_text="Timestamp when the current status was applied.",
    )
    valid_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Timestamp when the certificate became valid.",
    )
    revoked_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Timestamp when the certificate was revoked.",
    )
    expired_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Timestamp when the certificate expired.",
    )
    reissued_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Timestamp when the certificate was superseded by a new issue.",
    )
    status_reason = models.TextField(
        blank=True,
        help_text="Optional reason describing why the status was applied.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CertificateManager()

    class Meta:
        ordering = ("-issued_at", "-status_set_at", "-pk")
        verbose_name = "Consultant certificate"
        verbose_name_plural = "Consultant certificates"

    def __str__(self) -> str:  # pragma: no cover - human readable representation
        return f"Certificate<{self.consultant_id}:{self.get_status_display()}>"

    @property
    def is_active(self) -> bool:
        """Return ``True`` when the certificate is currently valid."""

        return self.status in self.ACTIVE_STATUSES

    def mark_status(
        self,
        status: str,
        *,
        reason: str | None = None,
        timestamp: datetime | None = None,
    ) -> None:
        """Apply a new status and persist timestamp bookkeeping."""

        now = timestamp or timezone.now()
        self.status = status
        self.status_set_at = now

        if status == self.Status.VALID:
            self.valid_at = self.valid_at or now
            self.revoked_at = None
            self.expired_at = None
        elif status == self.Status.REVOKED:
            self.revoked_at = now
        elif status == self.Status.EXPIRED:
            self.expired_at = now
        elif status == self.Status.REISSUED:
            self.reissued_at = now

        if reason is not None:
            self.status_reason = reason

        self.save(
            update_fields=[
                "status",
                "status_set_at",
                "valid_at",
                "revoked_at",
                "expired_at",
                "reissued_at",
                "status_reason",
                "updated_at",
            ]
        )


class Consultant(BaseConsultant):
    """Proxy model exposing scoped status choices for the API layer."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    class Meta:
        proxy = True
        verbose_name = BaseConsultant._meta.verbose_name  # type: ignore[attr-defined]
        verbose_name_plural = BaseConsultant._meta.verbose_name_plural  # type: ignore[attr-defined]


class LogEntry(BaseLogEntry):
    """Proxy exposing log entries in the public API layer."""

    class Meta:
        proxy = True
        verbose_name = BaseLogEntry._meta.verbose_name  # type: ignore[attr-defined]
        verbose_name_plural = BaseLogEntry._meta.verbose_name_plural  # type: ignore[attr-defined]


__all__ = ["Consultant", "LogEntry", "Certificate"]
