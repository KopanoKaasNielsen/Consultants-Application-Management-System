from django.urls import path
from . import views

urlpatterns = [
    path('apply/', views.submit_application, name='submit_application'),
    path('apply/draft/', views.autosave_consultant_draft, name='autosave_consultant_draft'),
]
