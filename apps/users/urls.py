from django.urls import path
from . import views
from .views import (
    RoleBasedLoginView,
    consultant_application_pdf,
    home_view,
    staff_consultant_pdf,
    staff_consultant_bulk_pdf,
    staff_dashboard_export_csv,
    staff_consultant_detail,
    staff_dashboard,
)

urlpatterns = [
    path('login/', RoleBasedLoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register, name='register'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('staff-dashboard/', staff_dashboard, name='staff_dashboard'),
    path('staff-dashboard/export/', staff_dashboard_export_csv, name='staff_dashboard_export'),
    path('staff/consultant/<int:pk>/', staff_consultant_detail, name='staff_consultant_detail'),
    path('staff/consultant/<int:pk>/pdf/', staff_consultant_pdf, name='staff_consultant_pdf'),
    path('staff/consultant/bulk-pdf/', staff_consultant_bulk_pdf, name='staff_consultant_bulk_pdf'),
    path('consultant/application/pdf/', consultant_application_pdf, name='consultant_application_pdf'),
    path('board/', views.board_dashboard, name='board_dashboard'),
    path('impersonation/', views.impersonation_dashboard, name='impersonation_dashboard'),
    path('impersonation/start/', views.start_impersonation, name='start_impersonation'),
    path('impersonation/stop/', views.stop_impersonation, name='stop_impersonation'),
    path('', home_view, name='home'),
]

