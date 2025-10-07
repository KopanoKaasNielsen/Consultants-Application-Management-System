from django.urls import path
from . import views
from .views import RoleBasedLoginView, home_view, staff_dashboard

urlpatterns = [
    path('login/', RoleBasedLoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register, name='register'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('staff-dashboard/', staff_dashboard, name='staff_dashboard'),
    path('board/', views.board_dashboard, name='board_dashboard'),
    path('impersonation/', views.impersonation_dashboard, name='impersonation_dashboard'),
    path('impersonation/start/', views.start_impersonation, name='start_impersonation'),
    path('impersonation/stop/', views.stop_impersonation, name='stop_impersonation'),
    path('', home_view, name='home'),
]

