from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import Consultant

@admin.register(Consultant)
class ConsultantAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'business_name', 'status', 'submitted_at')
    list_filter = ('status', 'nationality')
    search_fields = ('full_name', 'id_number', 'business_name')
