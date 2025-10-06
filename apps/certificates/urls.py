from django.urls import path

from . import views


app_name = "certificates"


urlpatterns = [
    path("", views.certificates_dashboard, name="certificates_dashboard"),
    path(
        "request-renewal/",
        views.request_certificate_renewal,
        name="request_renewal",
    ),
]
