"""
URL configuration for backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from consultant_app.views import (
    consultant_dashboard,
    log_entries,
    validate_consultant,
    verify_certificate,
)

from .health import database_health_view, health_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('health/', health_view, name='health'),
    path('health/database/', database_health_view, name='health-database'),
    path('', include('apps.users.urls')),
    path('consultants/', include('apps.consultants.urls')),
    path('certificates/', include(('apps.certificates.urls', 'certificates'), namespace='certificates')),
    path('officer/', include('apps.decisions.urls')),  # 👈 staff review routes
    path('vetting/', include('apps.vetting.urls')),
    path('verify/<uuid:certificate_uuid>/', verify_certificate, name='consultant-certificate-verify'),
    path('api/consultants/validate/', validate_consultant, name='consultant-validate'),
    path(
        'api/staff/consultants/',
        consultant_dashboard,
        name='consultant-dashboard',
    ),
    path(
        'api/staff/logs/',
        log_entries,
        name='consultant-log-entries',
    ),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
