from django.urls import path
from . import views

urlpatterns = [
    path('apply/', views.submit_application, name='submit_application'),
]
