from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from .views import home_view

urlpatterns = [
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register, name='register'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('impersonation/', views.impersonation_dashboard, name='impersonation_dashboard'),
    path('impersonation/start/', views.start_impersonation, name='start_impersonation'),
    path('impersonation/stop/', views.stop_impersonation, name='stop_impersonation'),
    path('', home_view, name='home'),
]

