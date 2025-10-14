"""API views for consultant validation and staff tooling."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date as date_type
from typing import Any, Dict, Iterable, List, Tuple
from uuid import UUID

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import CharField, Q, QuerySet
from django.db.models.functions import Cast
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_GET, require_POST

from apps.users.constants import UserRole
from apps.users.permissions import user_has_role
from consultant_app.certificates import CertificateTokenError, decode_certificate_metadata
from consultant_app.models import Certificate, Consultant, LogEntry
from consultant_app.serializers import (
    ConsultantDashboardSerializer,
    ConsultantValidationSerializer,
    LogEntrySerializer,
)

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


@dataclass(frozen=True)
class DashboardFilters:
    """Structured representation of filters applied to the dashboard."""

    statuses: List[str]
    date_from: date_type | None
    date_to: date_type | None
    search: str | None
    category: str | None
    sort: str


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


def build_dashboard_queryset(
    params,
) -> Tuple[QuerySet[Consultant], DashboardFilters]:
    """Return the filtered consultant queryset and applied filter metadata."""

    queryset = Consultant.objects.exclude(status=Consultant.Status.DRAFT)

    statuses = _split_status_filter(params.get("status"))
    if statuses:
        queryset = queryset.filter(status__in=statuses)

    category = (params.get("category") or "").strip()
    if category:
        queryset = queryset.filter(consultant_type__iexact=category)

    date_from = parse_date(params.get("date_from"))
    if date_from:
        queryset = queryset.filter(submitted_at__date__gte=date_from)

    date_to = parse_date(params.get("date_to"))
    if date_to:
        queryset = queryset.filter(submitted_at__date__lte=date_to)

    search_query = (params.get("search") or "").strip()
    if search_query:
        queryset = queryset.filter(
            Q(full_name__icontains=search_query)
            | Q(email__icontains=search_query)
            | Q(business_name__icontains=search_query)
        )

    sort_param = (params.get("sort") or "-date").strip()
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

    filters = DashboardFilters(
        statuses=statuses,
        date_from=date_from,
        date_to=date_to,
        search=search_query or None,
        category=category or None,
        sort=applied_sort,
    )

    return queryset, filters


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


def _user_is_staff(user) -> bool:
    return user_has_role(user, UserRole.STAFF) or getattr(user, "is_superuser", False)


@require_GET
def consultant_dashboard(request):
    """Return paginated consultant data for the staff dashboard."""

    queryset, filters = build_dashboard_queryset(request.GET)

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
                "status": filters.statuses,
                "date_from": filters.date_from.isoformat() if filters.date_from else None,
                "date_to": filters.date_to.isoformat() if filters.date_to else None,
                "category": filters.category,
                "search": filters.search,
                "sort": filters.sort,
            },
        }
    )


@require_GET
def search_certificate(request):
    """Render a public search portal for consultant certificates."""

    name_query = (request.GET.get("name") or "").strip()
    certificate_query = (request.GET.get("certificate_id") or "").strip()
    issue_date_query = (request.GET.get("issue_date") or "").strip()

    search_performed = any((name_query, certificate_query, issue_date_query))

    parsed_issue_date = None
    form_errors: Dict[str, str] = {}
    if issue_date_query:
        parsed_issue_date = parse_date(issue_date_query)
        if not parsed_issue_date:
            form_errors["issue_date"] = "Enter a valid date in YYYY-MM-DD format."

    results: List[Dict[str, Any]] = []

    if search_performed and not form_errors:
        queryset = (
            Certificate.objects.select_related("consultant")
            .filter(consultant__certificate_uuid__isnull=False)
        )

        if name_query:
            queryset = queryset.filter(consultant__full_name__icontains=name_query)

        if certificate_query:
            queryset = queryset.annotate(
                certificate_uuid_text=Cast(
                    "consultant__certificate_uuid",
                    output_field=CharField(),
                )
            ).filter(certificate_uuid_text__icontains=certificate_query)

        if parsed_issue_date:
            queryset = queryset.filter(issued_at__date=parsed_issue_date)

        queryset = queryset.order_by("-issued_at", "-status_set_at", "-pk")

        for certificate in queryset:
            issued_on = certificate.issued_at or certificate.consultant.certificate_generated_at
            if issued_on:
                issued_on = timezone.localtime(issued_on).date()

            results.append(
                {
                    "certificate_id": str(certificate.consultant.certificate_uuid),
                    "consultant_name": certificate.consultant.full_name,
                    "issued_on": issued_on,
                    "status": certificate.get_status_display(),
                    "status_code": certificate.status.upper(),
                    "verification_url": reverse(
                        "consultant-certificate-verify",
                        kwargs={
                            "certificate_uuid": certificate.consultant.certificate_uuid
                        },
                    ),
                }
            )

    context = {
        "form": {
            "name": name_query,
            "certificate_id": certificate_query,
            "issue_date": issue_date_query,
        },
        "form_errors": form_errors,
        "results": results,
        "result_count": len(results),
        "search_performed": search_performed,
    }

    return render(request, "certificates/search_certificate.html", context)


@require_GET
def verify_certificate(request, certificate_uuid: UUID):
    """Render a public verification page for consultant certificates."""

    consultant = get_object_or_404(Consultant, certificate_uuid=certificate_uuid)

    token = request.GET.get("token", "")
    verification_error = None
    issued_on = None
    verified = False

    certificate_id = str(consultant.certificate_uuid)
    expires_on = consultant.certificate_expires_at
    certificate_record = Certificate.objects.latest_for_consultant(consultant)
    certificate_status = certificate_record.status if certificate_record else Certificate.Status.REVOKED
    certificate_status_display = (
        certificate_record.get_status_display()
        if certificate_record
        else Certificate.Status.REVOKED.label
    )

    status_messages = {
        Certificate.Status.VALID: (
            "Certificate verified successfully.",
            200,
        ),
        Certificate.Status.REVOKED: (
            "This certificate has been revoked and is no longer valid.",
            410,
        ),
        Certificate.Status.EXPIRED: (
            "This certificate has expired and can no longer be verified.",
            410,
        ),
        Certificate.Status.REISSUED: (
            "This certificate has been replaced by a new issue.",
            409,
        ),
    }

    status_message, status_code = status_messages.get(
        certificate_status,
        ("Certificate status is unavailable.", 404),
    )

    status_effective_at = (
        certificate_record.status_set_at if certificate_record else None
    )
    status_reason = certificate_record.status_reason if certificate_record else ""

    if (
        not consultant.certificate_pdf
        or not certificate_record
        or not certificate_record.issued_at
    ):
        verification_error = "No active certificate found for this consultant."
        status_code = 404
    elif not token:
        verification_error = "Verification token is required."
        status_code = 400
    else:
        try:
            details = decode_certificate_metadata(token, consultant)
            issued_on = details.get("issued_on")
            metadata = details.get("metadata")
            if metadata:
                matched_record = Certificate.objects.matching_issue_timestamp(
                    consultant, metadata.issued_at
                )
                if matched_record:
                    certificate_record = matched_record
                    certificate_status = matched_record.status
                    certificate_status_display = matched_record.get_status_display()
                    status_message, status_code = status_messages.get(
                        certificate_status,
                        ("Certificate status is unavailable.", 404),
                    )
                    status_effective_at = matched_record.status_set_at
                    status_reason = matched_record.status_reason

            if certificate_status == Certificate.Status.VALID:
                verified = True
            else:
                verification_error = status_message
        except CertificateTokenError as exc:
            verification_error = str(exc)
            if certificate_status == Certificate.Status.VALID:
                status_code = 400

    if verification_error and certificate_status == Certificate.Status.VALID:
        status_message = verification_error

    context = {
        "consultant": consultant,
        "issued_on": issued_on,
        "expires_on": expires_on,
        "verified": verified,
        "verification_error": verification_error,
        "certificate_id": certificate_id,
        "certificate_status": certificate_status.upper(),
        "certificate_status_display": certificate_status_display,
        "certificate_status_message": status_message,
        "certificate_status_effective_at": status_effective_at,
        "certificate_status_reason": status_reason or None,
    }

    return render(
        request,
        "certificates/verification_detail.html",
        context,
        status=status_code,
    )


@login_required
@require_GET
def log_entries(request):
    """Return paginated structured log entries for authorised staff."""

    if not _user_is_staff(request.user):
        return JsonResponse({"detail": "Forbidden"}, status=403)

    queryset = LogEntry.objects.select_related("user").all()

    level = (request.GET.get("level") or "").strip().upper()
    if level:
        queryset = queryset.filter(level=level)

    logger_name = (request.GET.get("logger") or "").strip()
    if logger_name:
        queryset = queryset.filter(logger_name__icontains=logger_name)

    user_id = request.GET.get("user_id")
    if user_id and user_id.isdigit():
        queryset = queryset.filter(user_id=int(user_id))

    action = (request.GET.get("action") or "").strip()
    if action:
        queryset = queryset.filter(context__action=action)

    search_query = (request.GET.get("search") or "").strip()
    if search_query:
        queryset = queryset.filter(message__icontains=search_query)

    queryset = queryset.order_by("-timestamp", "-id")

    page = _parse_int(request.GET.get("page"), 1)
    page_size = min(_parse_int(request.GET.get("page_size"), DEFAULT_PAGE_SIZE), MAX_PAGE_SIZE)

    paginator = Paginator(queryset, page_size)
    page_obj = paginator.get_page(page)

    results = [LogEntrySerializer(entry).data for entry in page_obj.object_list]

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
                "level": level or None,
                "logger": logger_name or None,
                "user_id": int(user_id) if user_id and user_id.isdigit() else None,
                "action": action or None,
                "search": search_query or None,
            },
        }
    )

