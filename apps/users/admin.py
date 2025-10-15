"""Admin registrations for the users app."""

from django.contrib import admin

from apps.security.models import AuditLog
from apps.users.models import BoardMemberProfile


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


@admin.register(BoardMemberProfile)
class BoardMemberProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "signature_present", "updated_at")
    search_fields = ("user__username", "user__email", "user__first_name", "user__last_name")
    readonly_fields = ("created_at", "updated_at")

    def signature_present(self, obj):
        return bool(obj.signature_image)

    signature_present.boolean = True
    signature_present.short_description = "Has signature"
