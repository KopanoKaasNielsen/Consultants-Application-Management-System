from django.urls import path

from . import views


app_name = "certificates"


urlpatterns = [
    path("", views.certificates_dashboard, name="certificates_dashboard"),
]
