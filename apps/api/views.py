"""DRF views providing the public API surface."""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.db import connections
from django.db.models import Q
from django.db.utils import OperationalError
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.api.permissions import IsStaffUserRole
from apps.api.throttling import RoleBasedRateThrottle
from apps.api.serializers import (
    ConsultantDashboardListSerializer,
    ConsultantValidationErrorSerializer,
    ConsultantValidationSuccessSerializer,
    LogEntryListSerializer,
)
from consultant_app.serializers import (
    ConsultantDashboardSerializer,
    ConsultantValidationSerializer,
    LogEntrySerializer as LegacyLogEntrySerializer,
)
from consultant_app.utils.report_exporter import (
    build_dashboard_csv,
    describe_filters,
    render_dashboard_pdf,
    summarise_rows,
)
from consultant_app.views import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    _flatten_errors,
    _parse_int,
    build_dashboard_queryset,
)
from consultant_app.views.reports import _build_filename, _prepare_export_rows
from consultant_app.models import LogEntry

from apps.security.models import AuditLog


class HealthSummaryView(APIView):
    """Provide a JSON summary of the application's core health signals."""

    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):  # type: ignore[override]
        timestamp = timezone.now()

        database_status = "ok"
        overall_status = "ok"
        connection = connections["default"]
        try:
            if connection.connection is not None and connection.is_usable():
                database_status = "ok"
            else:
                with connection.cursor():
                    database_status = "ok"
        except OperationalError:
            database_status = "unavailable"
            overall_status = "degraded"

        fifteen_minutes_ago = timestamp - timedelta(minutes=15)
        severity_filter = Q(context__severity__iexact="critical") | Q(
            context__severity__iexact="high"
        )
        critical_action_filter = Q(
            action_code__in=getattr(settings, "SECURITY_ALERT_CRITICAL_ACTIONS", set())
        )
        login_failure_filter = Q(action_code=AuditLog.ActionCode.LOGIN_FAILURE) & Q(
            context__failure_count__gte=getattr(
                settings, "SECURITY_ALERT_LOGIN_FAILURE_THRESHOLD", 5
            )
        )
        recent_critical = AuditLog.objects.filter(
            Q(timestamp__gte=fifteen_minutes_ago)
            & (severity_filter | critical_action_filter | login_failure_filter)
        ).count()

        payload = {
            "status": overall_status,
            "timestamp": timestamp.isoformat(),
            "database": database_status,
            "recent_critical_events": recent_critical,
        }

        return Response(payload)


class ConsultantValidationView(APIView):
    """Validate consultant identifiers for uniqueness conflicts."""

    permission_classes = [permissions.AllowAny]
    throttle_classes = [RoleBasedRateThrottle]

    def post(self, request, *args, **kwargs):  # type: ignore[override]
        serializer = ConsultantValidationSerializer(request.data)
        if serializer.is_valid():
            response = ConsultantValidationSuccessSerializer(data={"valid": True})
            response.is_valid(raise_exception=True)
            return Response(response.data, status=status.HTTP_200_OK)

        errors = _flatten_errors(serializer.errors)
        error_serializer = ConsultantValidationErrorSerializer(data={"errors": errors})
        error_serializer.is_valid(raise_exception=True)
        return Response(error_serializer.data, status=status.HTTP_400_BAD_REQUEST)


class StaffConsultantViewSet(viewsets.ViewSet):
    """Provide staff access to consultant dashboard data."""

    permission_classes = [permissions.IsAuthenticated, IsStaffUserRole]
    throttle_classes = [RoleBasedRateThrottle]

    def list(self, request):  # type: ignore[override]
        queryset, filters = build_dashboard_queryset(request.query_params)

        page = _parse_int(request.query_params.get("page"), 1)
        page_size = min(
            _parse_int(request.query_params.get("page_size"), DEFAULT_PAGE_SIZE),
            MAX_PAGE_SIZE,
        )

        paginator = self._build_paginator(queryset, page_size)
        page_obj = paginator.get_page(page)

        results = [ConsultantDashboardSerializer(item).data for item in page_obj.object_list]

        payload = {
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

        response_serializer = ConsultantDashboardListSerializer(data=payload)
        response_serializer.is_valid(raise_exception=True)
        return Response(response_serializer.data)

    @staticmethod
    def _build_paginator(queryset, page_size):
        from django.core.paginator import Paginator

        return Paginator(queryset, page_size)


class StaffLogEntryViewSet(viewsets.ViewSet):
    """Expose application log entries for staff dashboards."""

    permission_classes = [permissions.IsAuthenticated, IsStaffUserRole]
    throttle_classes = [RoleBasedRateThrottle]

    def list(self, request):  # type: ignore[override]
        queryset = LogEntry.objects.select_related("user").all()

        level = (request.query_params.get("level") or "").strip().upper()
        if level:
            queryset = queryset.filter(level=level)

        logger_name = (request.query_params.get("logger") or "").strip()
        if logger_name:
            queryset = queryset.filter(logger_name__icontains=logger_name)

        user_id = request.query_params.get("user_id")
        if user_id and user_id.isdigit():
            queryset = queryset.filter(user_id=int(user_id))

        action = (request.query_params.get("action") or "").strip()
        if action:
            queryset = queryset.filter(context__action=action)

        search_query = (request.query_params.get("search") or "").strip()
        if search_query:
            queryset = queryset.filter(message__icontains=search_query)

        queryset = queryset.order_by("-timestamp", "-id")

        page = _parse_int(request.query_params.get("page"), 1)
        page_size = min(
            _parse_int(request.query_params.get("page_size"), DEFAULT_PAGE_SIZE),
            MAX_PAGE_SIZE,
        )

        paginator = StaffConsultantViewSet._build_paginator(queryset, page_size)
        page_obj = paginator.get_page(page)

        results = [LegacyLogEntrySerializer(entry).data for entry in page_obj.object_list]

        payload = {
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

        response_serializer = LogEntryListSerializer(data=payload)
        response_serializer.is_valid(raise_exception=True)
        return Response(response_serializer.data)


class ConsultantDashboardPDFExportView(APIView):
    """Generate the consultant dashboard export as a PDF document."""

    permission_classes = [permissions.IsAuthenticated, IsStaffUserRole]
    throttle_classes = [RoleBasedRateThrottle]

    def get(self, request, *args, **kwargs):  # type: ignore[override]
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
        response["Content-Disposition"] = (
            f'attachment; filename="{_build_filename("consultant-dashboard", "pdf")}"'
        )
        return response


class ConsultantDashboardCSVExportView(APIView):
    """Generate the consultant dashboard export as a CSV document."""

    permission_classes = [permissions.IsAuthenticated, IsStaffUserRole]
    throttle_classes = [RoleBasedRateThrottle]

    def get(self, request, *args, **kwargs):  # type: ignore[override]
        rows, _filters = _prepare_export_rows(request)
        csv_bytes = build_dashboard_csv(rows)

        response = HttpResponse(csv_bytes, content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="{_build_filename("consultant-dashboard", "csv")}"'
        )
        return response
