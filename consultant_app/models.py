"""Database models and domain helpers for consultant APIs."""

from __future__ import annotations

from django.db import models

from apps.consultants.models import Consultant as BaseConsultant


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


__all__ = ["Consultant"]
