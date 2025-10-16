#!/usr/bin/env python3
"""Utility script for cleaning duplicate consultant records.

This helper is intended to be executed prior to applying the
``consultants_unique_email_per_nationality`` constraint in production. It
merges duplicate consultant records that share the same identifying fields,
reassigns related foreign keys, and removes the redundant rows.
"""

from __future__ import annotations

import logging
import os
from typing import Iterable, List, Sequence, Tuple

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings.prod")

import django  # noqa: E402  (needs settings configured before import)

django.setup()

from django.db import transaction  # noqa: E402
from django.db.models import Count  # noqa: E402
from django.db.utils import OperationalError, ProgrammingError  # noqa: E402

from apps.certificates.models import CertificateRenewal  # noqa: E402
from apps.consultants.models import Consultant

try:  # pragma: no cover - Document table may not be present in older schemas
    from apps.consultants.models import Document  # type: ignore
except Exception:  # pragma: no cover - module structure changed
    Document = None  # type: ignore[assignment]
from apps.decisions.models import ApplicationAction  # noqa: E402

try:  # pragma: no cover - optional dependency for patched deployments
    from consultant_app.models import Certificate as ConsultantCertificate
except Exception:  # pragma: no cover - the app may be missing in older setups
    ConsultantCertificate = None  # type: ignore[assignment]


LOGGER = logging.getLogger("consultant_cleanup")
logging.basicConfig(level=logging.INFO, format="%(message)s")

STATUS_PRIORITY = {
    "rejected": 0,
    "draft": 1,
    "incomplete": 2,
    "submitted": 3,
    "vetted": 4,
    "approved": 5,
}


def _status_rank(status: str | None) -> int:
    return STATUS_PRIORITY.get(status or "", -1)


def _timestamp(value) -> float:
    if value is None:
        return 0.0
    try:
        return float(value.timestamp())
    except Exception:  # pragma: no cover - platform dependent edge cases
        return 0.0


def _select_primary(candidates: Sequence[Consultant]) -> Consultant:
    def sort_key(instance: Consultant) -> Tuple[int, int, float, float, int]:
        return (
            _status_rank(instance.status),
            1 if instance.certificate_generated_at else 0,
            _timestamp(instance.submitted_at),
            _timestamp(instance.updated_at),
            -instance.pk,
        )

    return sorted(candidates, key=sort_key, reverse=True)[0]


def _merge_consultant(primary: Consultant, duplicate: Consultant) -> None:
    updated_fields: List[str] = []

    if _status_rank(duplicate.status) > _status_rank(primary.status):
        primary.status = duplicate.status
        updated_fields.append("status")

    if duplicate.is_seen_by_staff and not primary.is_seen_by_staff:
        primary.is_seen_by_staff = True
        updated_fields.append("is_seen_by_staff")

    # Prefer keeping the most complete record by copying missing fields.
    merge_fields = [
        "submitted_at",
        "certificate_generated_at",
        "certificate_expires_at",
        "certificate_pdf",
        "rejection_letter",
        "rejection_letter_generated_at",
        "staff_comment",
        "business_certificate",
        "photo",
        "id_document",
        "cv",
        "police_clearance",
        "qualifications",
        "consultant_type",
        "business_name",
        "registration_number",
    ]

    for field in merge_fields:
        primary_value = getattr(primary, field)
        duplicate_value = getattr(duplicate, field)
        if not primary_value and duplicate_value:
            setattr(primary, field, duplicate_value)
            updated_fields.append(field)

    if updated_fields:
        primary.save(update_fields=updated_fields)


def _reassign_related(primary: Consultant, duplicate: Consultant) -> None:
    related_models: List[Tuple[object, str]] = [
        (ApplicationAction, "consultant"),
        (CertificateRenewal, "consultant"),
    ]

    if Document:  # type: ignore[truthy-bool]
        related_models.append((Document, "application"))

    if ConsultantCertificate is not None:
        related_models.append((ConsultantCertificate, "consultant"))

    for model, field_name in related_models:
        try:
            model.objects.filter(**{field_name: duplicate}).update(**{field_name: primary})
        except (ProgrammingError, OperationalError):  # pragma: no cover - table missing
            LOGGER.debug("Skipping %s.%s reassignment; table unavailable", model.__name__, field_name)


def _dedupe_group(candidates: Iterable[Consultant]) -> Tuple[Consultant | None, List[int]]:
    candidates_list = list(candidates)
    if len(candidates_list) <= 1:
        return (candidates_list[0] if candidates_list else None), []

    primary = _select_primary(candidates_list)
    removed_ids: List[int] = []

    for duplicate in candidates_list:
        if duplicate.pk == primary.pk:
            continue

        _merge_consultant(primary, duplicate)
        _reassign_related(primary, duplicate)
        removed_ids.append(duplicate.pk)
        duplicate.delete()

    return primary, removed_ids


def _dedupe_by_fields(fields: Sequence[str]) -> Tuple[int, List[str]]:
    removed: List[str] = []
    Consultant.objects.all()  # touch queryset for type checking clarity

    duplicates = (
        Consultant.objects.values(*fields)
        .order_by()
        .annotate(total=Count("id"))
        .filter(total__gt=1)
    )

    total_removed = 0

    for entry in duplicates:
        filters = {field: entry[field] for field in fields}
        queryset = Consultant.objects.filter(**filters).order_by("-updated_at", "-pk")
        primary, removed_ids = _dedupe_group(queryset)

        if primary is not None and removed_ids:
            total_removed += len(removed_ids)
            description = ", ".join(f"{field}={filters[field]!r}" for field in fields)
            LOGGER.info(
                "Merged %s -> kept #%s, removed %s",
                description,
                primary.pk,
                removed_ids,
            )
            removed.append(description)

    return total_removed, removed


def main() -> None:
    LOGGER.info("Starting consultant deduplication cleanup…")

    with transaction.atomic():
        total_removed = 0

        for fields in (("email", "nationality"), ("user_id",), ("id_number",)):
            removed_count, _ = _dedupe_by_fields(fields)
            total_removed += removed_count

    if total_removed:
        LOGGER.info("Removed %s duplicate consultant records.", total_removed)
    else:
        LOGGER.info("No duplicate consultant records were found.")


if __name__ == "__main__":
    main()
