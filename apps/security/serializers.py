"""Serializers exposing security audit log records via the API."""

from __future__ import annotations

from rest_framework import serializers

from apps.security.models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    """Read-only representation of :class:`AuditLog` instances."""

    user_id = serializers.IntegerField(read_only=True)
    username = serializers.SerializerMethodField()
    action_display = serializers.CharField(
        source="get_action_code_display", read_only=True
    )

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "timestamp",
            "action_code",
            "action_display",
            "resolved_role",
            "target",
            "endpoint",
            "client_ip",
            "context",
            "user_id",
            "username",
        ]
        read_only_fields = fields

    def get_username(self, obj: AuditLog) -> str | None:
        user = obj.user
        if not user:
            return None
        return user.get_username()
