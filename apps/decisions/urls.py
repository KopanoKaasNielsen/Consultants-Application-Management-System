from django.urls import path
from . import views

urlpatterns = [
    path('applications/', views.applications_list, name='officer_applications_list'),
    path('applications/<int:pk>/', views.application_detail, name='officer_application_detail'),
]
from django.urls import path
from . import views

urlpatterns = [
    path('applications/', views.applications_list, name='officer_applications_list'),
    path('applications/<int:pk>/', views.application_detail, name='officer_application_detail'),
]
