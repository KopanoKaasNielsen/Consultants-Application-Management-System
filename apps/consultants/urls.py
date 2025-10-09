from django.urls import path
from . import views

urlpatterns = [
    path('apply/', views.submit_application, name='submit_application'),
    path('apply/draft/', views.autosave_consultant_draft, name='autosave_consultant_draft'),
    path(
        'notifications/<int:notification_id>/read/',
        views.mark_notification_read,
        name='consultant_notification_mark_read',
    ),
]
