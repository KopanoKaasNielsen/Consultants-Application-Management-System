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
    path(
        'applications/<int:application_id>/documents/upload/',
        views.upload_document,
        name='consultant_document_upload',
    ),
    path(
        'documents/<uuid:document_id>/delete/',
        views.delete_document,
        name='consultant_document_delete',
    ),
    path(
        'documents/<uuid:document_id>/download/',
        views.download_document,
        name='consultant_document_download',
    ),
    path(
        'documents/<uuid:document_id>/preview/',
        views.preview_document,
        name='consultant_document_preview',
    ),
]
