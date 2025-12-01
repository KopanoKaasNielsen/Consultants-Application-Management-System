from django.urls import path

from .views import workflow_status

app_name = "officer_workflow"

urlpatterns = [
    path("status/", workflow_status, name="workflow_status"),
]
