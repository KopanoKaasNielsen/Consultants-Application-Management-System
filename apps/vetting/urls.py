from django.urls import path

from .views import vetting_dashboard


urlpatterns = [
    path("", vetting_dashboard, name="vetting_dashboard"),
]
