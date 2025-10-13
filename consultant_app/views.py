"""API views for consultant validation."""

from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List

from django.http import JsonResponse
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_GET, require_POST
from django.core.paginator import Paginator
from django.db.models import Q

from consultant_app.models import Consultant

from .serializers import (
    ConsultantDashboardSerializer,
    ConsultantValidationSerializer,
)

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def _parse_int(value: str | None, default: int) -> int:
    try:
        if value is None:
            return default
        parsed = int(value)
        return parsed if parsed > 0 else default
    except (TypeError, ValueError):
        return default


def _split_status_filter(value: str | None) -> List[str]:
    if not value:
        return []
    statuses = [item.strip() for item in value.split(",")]
    return [status for status in statuses if status]


def _serialize_page(results: Iterable[Consultant]) -> List[Dict[str, Any]]:
    return [ConsultantDashboardSerializer(result).data for result in results]


def _flatten_errors(errors: Dict[str, Any]) -> Dict[str, str]:
    """Return a flattened mapping of validation errors."""

    flattened: Dict[str, str] = {}
    for field, messages in errors.items():
        if isinstance(messages, (list, tuple)):
            flattened[field] = str(messages[0]) if messages else ""
        else:
            flattened[field] = str(messages)
    return flattened


@require_POST
def validate_consultant(request):
    """Validate consultant fields for uniqueness constraints."""

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse(
            {"errors": {"non_field_errors": "Invalid JSON payload."}},
            status=400,
        )

    serializer = ConsultantValidationSerializer(payload)

    if serializer.is_valid():
        return JsonResponse({"valid": True})

    errors = _flatten_errors(serializer.errors)
    return JsonResponse({"errors": errors}, status=400)


@require_GET
def consultant_dashboard(request):
    """Return paginated consultant data for the staff dashboard."""

    queryset = Consultant.objects.exclude(status=Consultant.Status.DRAFT)

    statuses = _split_status_filter(request.GET.get("status"))
    if statuses:
        queryset = queryset.filter(status__in=statuses)

    date_from = parse_date(request.GET.get("date_from"))
    if date_from:
        queryset = queryset.filter(submitted_at__date__gte=date_from)

    date_to = parse_date(request.GET.get("date_to"))
    if date_to:
        queryset = queryset.filter(submitted_at__date__lte=date_to)

    search_query = (request.GET.get("search") or "").strip()
    if search_query:
        queryset = queryset.filter(
            Q(full_name__icontains=search_query)
            | Q(email__icontains=search_query)
            | Q(business_name__icontains=search_query)
        )

    sort_param = (request.GET.get("sort") or "-date").strip()
    sort_field_map = {
        "name": "full_name",
        "email": "email",
        "status": "status",
        "date": "submitted_at",
        "updated": "updated_at",
    }

    descending = False
    if sort_param.startswith("-"):
        descending = True
        sort_param = sort_param[1:]

    sort_field = sort_field_map.get(sort_param)
    if not sort_field:
        sort_field = "submitted_at"
        descending = True
        applied_sort = "-date"
    else:
        applied_sort = f"-{sort_param}" if descending else sort_param

    if descending:
        sort_field = f"-{sort_field}"

    queryset = queryset.order_by(sort_field, "-id")

    page = _parse_int(request.GET.get("page"), 1)
    page_size = min(_parse_int(request.GET.get("page_size"), DEFAULT_PAGE_SIZE), MAX_PAGE_SIZE)

    paginator = Paginator(queryset, page_size)
    page_obj = paginator.get_page(page)

    results = _serialize_page(page_obj.object_list)

    return JsonResponse(
        {
            "results": results,
            "pagination": {
                "page": page_obj.number,
                "page_size": page_obj.paginator.per_page,
                "total_pages": page_obj.paginator.num_pages,
                "total_results": page_obj.paginator.count,
                "has_next": page_obj.has_next(),
                "has_previous": page_obj.has_previous(),
            },
            "applied_filters": {
                "status": statuses,
                "date_from": date_from.isoformat() if date_from else None,
                "date_to": date_to.isoformat() if date_to else None,
                "search": search_query or None,
                "sort": applied_sort,
            },
        }
    )

