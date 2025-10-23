from django.urls import path
from . import views

app_name = 'certificates'

urlpatterns = [
    path('generate/', views.generate_certificate, name='generate'),
]
