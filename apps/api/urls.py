"""URL configuration for the API application."""

from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.api.views import (
    ConsultantDashboardCSVExportView,
    ConsultantDashboardPDFExportView,
    ConsultantValidationView,
    HealthSummaryView,
    ServiceMetricsView,
    StaffConsultantViewSet,
    StaffLogEntryViewSet,
)
from apps.security.views import AuditLogViewSet

router = DefaultRouter()
router.register('staff/consultants', StaffConsultantViewSet, basename='staff-consultants')
router.register('staff/logs', StaffLogEntryViewSet, basename='staff-logs')
router.register('audit-logs', AuditLogViewSet, basename='audit-logs')

app_name = 'api'

urlpatterns = [
    path('', include(router.urls)),
    path('health/', HealthSummaryView.as_view(), name='health-summary'),
    path('metrics/', ServiceMetricsView.as_view(), name='service-metrics'),
    path('consultants/validate/', ConsultantValidationView.as_view(), name='consultant-validate'),
    path(
        'staff/consultants/export/pdf/',
        ConsultantDashboardPDFExportView.as_view(),
        name='consultant-dashboard-export-pdf',
    ),
    path(
        'staff/consultants/export/csv/',
        ConsultantDashboardCSVExportView.as_view(),
        name='consultant-dashboard-export-csv',
    ),
]
