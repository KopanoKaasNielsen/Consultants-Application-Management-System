"""Utilities for exporting consultant dashboard reports."""

from __future__ import annotations

import csv
import io
from collections import Counter
from typing import Any, Dict, List, Sequence

from django.utils import timezone
from django.template.loader import render_to_string
from weasyprint import HTML

from apps.consultants.models import Consultant as BaseConsultant
from consultant_app.models import Certificate, Consultant
from consultant_app.serializers import ConsultantDashboardSerializer
from consultant_app.views import DashboardFilters

DATE_FORMAT = "%Y-%m-%d"
DATETIME_FORMAT = "%Y-%m-%d %H:%M"
STATUS_LABELS = dict(BaseConsultant.STATUS_CHOICES)
SORT_LABELS = {
    "-date": "Newest submissions",
    "date": "Oldest submissions",
    "name": "Name (A–Z)",
    "-name": "Name (Z–A)",
    "email": "Email (A–Z)",
    "-email": "Email (Z–A)",
    "status": "Status (A–Z)",
    "-status": "Status (Z–A)",
    "updated": "Last updated (oldest first)",
    "-updated": "Last updated (newest first)",
}


def _localize_datetime(value):
    if not value:
        return None
    if timezone.is_aware(value):
        return timezone.localtime(value)
    return value


def _format_datetime_display(value) -> str:
    localized = _localize_datetime(value)
    return localized.strftime(DATETIME_FORMAT) if localized else "—"


def _isoformat(value) -> str:
    localized = _localize_datetime(value)
    return localized.isoformat() if localized else ""


def _format_date_display(value) -> str:
    return value.strftime(DATE_FORMAT) if value else "—"


def _latest_certificate(consultant: Consultant) -> Certificate | None:
    cache = getattr(consultant, "_prefetched_objects_cache", {})
    if cache and "certificate_records" in cache:
        records = cache["certificate_records"]
        return records[0] if records else None
    return Certificate.objects.latest_for_consultant(consultant)


def prepare_dashboard_rows(consultants: Sequence[Consultant]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for consultant in consultants:
        serializer = ConsultantDashboardSerializer(consultant)
        data = serializer.data
        certificate = _latest_certificate(consultant)

        certificate_status_display = (
            certificate.get_status_display() if certificate else "Not issued"
        )
        certificate_status_code = certificate.status.upper() if certificate else ""
        certificate_issued_display = (
            _format_datetime_display(certificate.issued_at) if certificate else "—"
        )
        certificate_issued_iso = _isoformat(certificate.issued_at) if certificate else ""

        documents = data["documents"]
        documents_summary = (
            "Complete"
            if documents["is_complete"]
            else f"Missing: {', '.join(documents['missing'])}"
        )

        rows.append(
            {
                "name": consultant.full_name,
                "email": consultant.email,
                "status": consultant.status,
                "status_display": consultant.get_status_display(),
                "consultant_type": consultant.consultant_type or None,
                "submitted_iso": data["submitted_at"] or "",
                "updated_iso": data["updated_at"] or "",
                "submitted_display": _format_datetime_display(consultant.submitted_at),
                "updated_display": _format_datetime_display(consultant.updated_at),
                "certificate_id": str(consultant.certificate_uuid) if consultant.certificate_uuid else "",
                "certificate_status": certificate_status_display,
                "certificate_status_code": certificate_status_code,
                "certificate_issued_iso": certificate_issued_iso,
                "certificate_issued_display": certificate_issued_display,
                "certificate_expires_iso": data["certificate_expires_at"] or "",
                "certificate_expires_display": _format_date_display(
                    consultant.certificate_expires_at
                ),
                "certificate_reason": data.get("certificate_status_reason") or "",
                "documents_complete": documents["is_complete"],
                "documents_summary": documents_summary,
                "missing_documents": documents["missing"],
            }
        )
    return rows


def summarise_rows(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(rows)
    status_counter = Counter(row["status"] for row in rows)
    statuses = []
    for code, count in sorted(status_counter.items(), key=lambda item: STATUS_LABELS.get(item[0], item[0])):
        label = STATUS_LABELS.get(code, code.replace("_", " ").title())
        percentage = round((count / total) * 100, 1) if total else 0.0
        statuses.append(
            {
                "code": code,
                "label": label,
                "count": count,
                "percentage": percentage,
            }
        )

    category_counter = Counter((row["consultant_type"] or "Unspecified") for row in rows)
    categories = []
    for label, count in sorted(category_counter.items(), key=lambda item: item[0].lower()):
        percentage = round((count / total) * 100, 1) if total else 0.0
        categories.append(
            {
                "label": label,
                "count": count,
                "percentage": percentage,
            }
        )

    complete_documents = sum(1 for row in rows if row["documents_complete"])

    return {
        "total": total,
        "statuses": statuses,
        "categories": categories,
        "documents": {
            "complete": complete_documents,
            "incomplete": total - complete_documents,
        },
    }


def describe_filters(filters: DashboardFilters) -> List[Dict[str, str]]:
    status_value: str
    if filters.statuses:
        labels = [STATUS_LABELS.get(code, code.title()) for code in filters.statuses]
        status_value = ", ".join(labels)
    else:
        status_value = "All statuses"

    if filters.date_from or filters.date_to:
        start = filters.date_from.strftime(DATE_FORMAT) if filters.date_from else "Any"
        end = filters.date_to.strftime(DATE_FORMAT) if filters.date_to else "Any"
        date_range = f"{start} → {end}"
    else:
        date_range = "All time"

    category_value = filters.category or "All categories"
    search_value = filters.search or "None"
    sort_value = SORT_LABELS.get(filters.sort, filters.sort)

    return [
        {"label": "Status", "value": status_value},
        {"label": "Date range", "value": date_range},
        {"label": "Consultant type", "value": category_value},
        {"label": "Search query", "value": search_value},
        {"label": "Sort order", "value": sort_value},
    ]


def render_dashboard_pdf(
    *,
    rows: Sequence[Dict[str, Any]],
    filters: Sequence[Dict[str, str]],
    summary: Dict[str, Any],
    generated_at,
    base_url: str,
) -> bytes:
    html = render_to_string(
        "reports/dashboard_pdf.html",
        {
            "rows": rows,
            "filters": filters,
            "summary": summary,
            "generated_at": generated_at,
        },
    )
    return HTML(string=html, base_url=base_url).write_pdf()


def build_dashboard_csv(rows: Sequence[Dict[str, Any]]) -> bytes:
    headers = [
        "Full name",
        "Email",
        "Status",
        "Consultant type",
        "Submitted at",
        "Last updated",
        "Certificate ID",
        "Certificate status",
        "Certificate issued at",
        "Certificate expires",
        "Certificate reason",
        "Documents",
    ]

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=headers, lineterminator="\n")
    writer.writeheader()

    for row in rows:
        writer.writerow(
            {
                "Full name": row["name"],
                "Email": row["email"],
                "Status": row["status_display"],
                "Consultant type": row["consultant_type"] or "Unspecified",
                "Submitted at": row["submitted_iso"],
                "Last updated": row["updated_iso"],
                "Certificate ID": row["certificate_id"],
                "Certificate status": row["certificate_status"],
                "Certificate issued at": row["certificate_issued_iso"],
                "Certificate expires": row["certificate_expires_iso"],
                "Certificate reason": row["certificate_reason"],
                "Documents": row["documents_summary"],
            }
        )

    return buffer.getvalue().encode("utf-8")


