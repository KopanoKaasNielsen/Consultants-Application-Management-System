"""Admin registrations for the users app."""

from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "user", "action_type", "target_object")
    list_filter = ("action_type", "timestamp")
    search_fields = ("user__username", "target_object", "metadata")
    readonly_fields = ("timestamp",)
