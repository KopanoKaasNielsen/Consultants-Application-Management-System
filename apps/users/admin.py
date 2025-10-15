"""Admin registrations for the users app."""

from django.contrib import admin

from apps.security.models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = (
        "timestamp",
        "user",
        "resolved_role",
        "action_code",
        "endpoint",
        "client_ip",
        "target",
    )
    list_filter = ("action_code", "resolved_role", "timestamp")
    search_fields = (
        "user__username",
        "user__email",
        "target",
        "context",
        "endpoint",
    )
    readonly_fields = ("timestamp",)
