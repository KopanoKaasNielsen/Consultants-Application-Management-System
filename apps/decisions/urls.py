from django.urls import path

from . import views

urlpatterns = [
    path("dashboard/", views.decisions_dashboard, name="decisions_dashboard"),
    path("applications/", views.applications_list, name="officer_applications_list"),
    path(
        "applications/<int:pk>/",
        views.application_detail,
        name="officer_application_detail",
    ),
    path(
        "renewals/",
        views.renewal_requests,
        name="certificate_renewal_requests",
    ),
]
