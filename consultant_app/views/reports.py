"""Views for exporting consultant dashboard data."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

from consultant_app.utils.report_exporter import (
    build_dashboard_csv,
    describe_filters,
    prepare_dashboard_rows,
    render_dashboard_pdf,
    summarise_rows,
)

from . import _user_is_staff, build_dashboard_queryset


def _build_filename(prefix: str, extension: str) -> str:
    timestamp = timezone.now().strftime("%Y%m%d-%H%M%S")
    return f"{prefix}-{timestamp}.{extension}"


def _prepare_export_rows(request):
    queryset, filters = build_dashboard_queryset(request.GET)
    queryset = queryset.select_related("user").prefetch_related("certificate_records")
    consultants = list(queryset)
    rows = prepare_dashboard_rows(consultants)
    return rows, filters


@login_required
@require_GET
def export_consultant_dashboard_pdf(request):
    if not _user_is_staff(request.user):
        return JsonResponse({"detail": "Forbidden"}, status=403)

    rows, filters = _prepare_export_rows(request)
    summary = summarise_rows(rows)
    filter_descriptions = describe_filters(filters)
    generated_at = timezone.localtime(timezone.now())

    pdf_bytes = render_dashboard_pdf(
        rows=rows,
        filters=filter_descriptions,
        summary=summary,
        generated_at=generated_at,
        base_url=request.build_absolute_uri("/"),
    )

    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    filename_pdf = _build_filename("consultant-dashboard", "pdf")
    response["Content-Disposition"] = f"attachment; filename={filename_pdf}"
    return response


@login_required
@require_GET
def export_consultant_dashboard_csv(request):
    if not _user_is_staff(request.user):
        return JsonResponse({"detail": "Forbidden"}, status=403)

    rows, _filters = _prepare_export_rows(request)
    csv_bytes = build_dashboard_csv(rows)

    response = HttpResponse(csv_bytes, content_type="text/csv")
    filename_csv = _build_filename("consultant-dashboard", "csv")
    response["Content-Disposition"] = f"attachment; filename={filename_csv}"
    return response
