from django.contrib import admin
from .models import Consultant, LogEntry, Notification

@admin.register(Consultant)
class ConsultantAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'business_name', 'status', 'submitted_at')
    list_filter = ('status', 'nationality')
    search_fields = ('full_name', 'id_number', 'business_name')


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        "recipient",
        "notification_type",
        "is_read",
        "delivered_at",
        "read_at",
    )
    list_filter = ("notification_type", "is_read")
    search_fields = ("recipient__username", "message")


@admin.register(LogEntry)
class LogEntryAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "level", "logger_name", "user", "message")
    list_filter = ("timestamp", "level", "user")
    search_fields = ("message", "logger_name", "context")
    date_hierarchy = "timestamp"
    readonly_fields = ("timestamp", "level", "logger_name", "message", "context", "user")
