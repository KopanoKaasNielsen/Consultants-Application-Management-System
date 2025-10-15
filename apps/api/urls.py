"""URL configuration for the API application."""

from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.api.views import (
    ConsultantDashboardCSVExportView,
    ConsultantDashboardPDFExportView,
    ConsultantValidationView,
    StaffConsultantViewSet,
    StaffLogEntryViewSet,
)

router = DefaultRouter()
router.register('staff/consultants', StaffConsultantViewSet, basename='staff-consultants')
router.register('staff/logs', StaffLogEntryViewSet, basename='staff-logs')

app_name = 'api'

urlpatterns = [
    path('', include(router.urls)),
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
