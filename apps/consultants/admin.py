from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import Consultant, Notification

@admin.register(Consultant)
class ConsultantAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'business_name', 'status', 'submitted_at')
    list_filter = ('status', 'nationality')
    search_fields = ('full_name', 'id_number', 'business_name')


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("recipient", "notification_type", "is_read", "created_at")
    list_filter = ("notification_type", "is_read")
    search_fields = ("recipient__username", "message")
