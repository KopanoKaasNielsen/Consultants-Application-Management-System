"""DRF viewsets providing access to the security audit logs."""

from __future__ import annotations

from rest_framework import mixins, permissions, viewsets
from rest_framework.pagination import PageNumberPagination

from apps.api.permissions import IsAdminUserRole
from apps.api.throttling import RoleBasedRateThrottle
from apps.security.models import AuditLog
from apps.security.serializers import AuditLogSerializer


class AuditLogPagination(PageNumberPagination):
    """Default pagination settings for audit log listings."""

    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200


class AuditLogViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Provide a paginated, read-only view of security audit logs."""

    queryset = AuditLog.objects.select_related("user").all()
    serializer_class = AuditLogSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminUserRole]
    throttle_classes = [RoleBasedRateThrottle]
    pagination_class = AuditLogPagination
