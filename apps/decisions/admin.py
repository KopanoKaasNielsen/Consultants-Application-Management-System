from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import ApplicationAction

@admin.register(ApplicationAction)
class ApplicationActionAdmin(admin.ModelAdmin):
    list_display = ('consultant', 'action', 'actor', 'created_at')
    list_filter = ('action', 'created_at')
    search_fields = ('consultant__full_name', 'actor__username', 'notes')

