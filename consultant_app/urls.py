from django.urls import path

from .views import search_certificate

app_name = "consultant_app"

urlpatterns = [
    path("search-certificate/", search_certificate, name="certificate-search"),
]
