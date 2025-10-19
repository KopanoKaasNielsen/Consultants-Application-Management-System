"""Admin configuration for consultant workflows and certificate records."""
from __future__ import annotations

from django import forms
from django.contrib import admin, messages
from django.contrib.admin.helpers import ActionForm
from django.db.models import OuterRef, Subquery
from django.utils.text import Truncator
from django.utils.translation import ngettext

from consultant_app.models import Certificate
from consultant_app.tasks import (
    reissue_certificate_task,
    revoke_certificate_task,
)

from .models import Consultant, LogEntry, Notification


class ConsultantAdminActionForm(ActionForm):
    """Expose additional inputs for consultant certificate admin actions."""

    reason = forms.CharField(
        required=True,
        label="Reason for certificate status change",
        help_text="Provide a justification when revoking or reissuing a certificate.",
        widget=forms.Textarea(attrs={"rows": 2}),
    )


@admin.register(Consultant)
class ConsultantAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "business_name",
        "status",
        "submitted_at",
        "certificate_status_display",
        "certificate_status_updated",
        "certificate_status_reason_short",
    )
    list_filter = ("status", "nationality")
    search_fields = ("full_name", "id_number", "business_name")
    actions = [
        "action_mark_certificate_revoked",
        "action_mark_certificate_reissued",
    ]
    action_form = ConsultantAdminActionForm

    def get_queryset(self, request):  # type: ignore[override]
        queryset = super().get_queryset(request)
        latest_certificate = (
            Certificate.objects.filter(consultant=OuterRef("pk"))
            .order_by("-issued_at", "-status_set_at", "-pk")
        )
        return queryset.annotate(
            latest_certificate_id=Subquery(latest_certificate.values("id")[:1]),
            latest_certificate_status=Subquery(
                latest_certificate.values("status")[:1]
            ),
            latest_certificate_reason=Subquery(
                latest_certificate.values("status_reason")[:1]
            ),
            latest_certificate_status_set_at=Subquery(
                latest_certificate.values("status_set_at")[:1]
            ),
        )

    def get_fields(self, request, obj=None):  # type: ignore[override]
        base_fields = super().get_fields(request, obj)
        fields = list(base_fields or [])
        for field in (
            "certificate_status_display",
            "certificate_status_reason_display",
            "certificate_status_updated",
        ):
            if field not in fields:
                fields.append(field)
        return fields

    def get_readonly_fields(self, request, obj=None):  # type: ignore[override]
        readonly = set(super().get_readonly_fields(request, obj))
        readonly.update(
            {
                "certificate_status_display",
                "certificate_status_reason_display",
                "certificate_status_updated",
            }
        )
        return tuple(sorted(readonly))

    @admin.display(description="Certificate status", ordering="latest_certificate_status")
    def certificate_status_display(self, obj: Consultant) -> str:
        status_value = getattr(obj, "latest_certificate_status", None)
        if not status_value:
            return "—"
        try:
            status_choice = Certificate.Status(status_value)
        except ValueError:  # pragma: no cover - safeguard against legacy values
            return status_value
        return status_choice.label

    @admin.display(description="Certificate status reason")
    def certificate_status_reason_display(self, obj: Consultant) -> str:
        reason = getattr(obj, "latest_certificate_reason", "")
        return reason or "—"

    @admin.display(
        description="Certificate reason",
        ordering="latest_certificate_reason",
    )
    def certificate_status_reason_short(self, obj: Consultant) -> str:
        reason = getattr(obj, "latest_certificate_reason", "") or "—"
        return Truncator(reason).chars(60)

    @admin.display(description="Certificate updated", ordering="latest_certificate_status_set_at")
    def certificate_status_updated(self, obj: Consultant):
        return getattr(obj, "latest_certificate_status_set_at", None)

    @admin.action(description="Revoke certificate and log a reason")
    def action_mark_certificate_revoked(self, request, queryset):
        return self._execute_certificate_status_action(
            request,
            queryset,
            status=Certificate.Status.REVOKED,
        )

    @admin.action(description="Mark certificate as reissued")
    def action_mark_certificate_reissued(self, request, queryset):
        return self._execute_certificate_status_action(
            request,
            queryset,
            status=Certificate.Status.REISSUED,
        )

    def _execute_certificate_status_action(self, request, queryset, *, status):
        reason = (request.POST.get("reason") or "").strip()
        if not reason:
            self.message_user(
                request,
                "Please provide a reason for the certificate status change.",
                level=messages.ERROR,
            )
            return None

        applied = 0
        missing = 0
        for consultant in queryset:
            latest_certificate = Certificate.objects.latest_for_consultant(consultant)
            if not latest_certificate:
                missing += 1
                continue

            metadata = {
                "source": "admin",
                "admin_action": f"{self.__class__.__name__}.{status.value}",
            }

            try:
                if status == Certificate.Status.REVOKED:
                    revoke_certificate_task.delay(
                        consultant.pk,
                        reason=reason,
                        actor_id=request.user.pk,
                        notify_consultant=True,
                        metadata=metadata,
                    )
                elif status == Certificate.Status.REISSUED:
                    reissue_certificate_task.delay(
                        consultant.pk,
                        reason=reason,
                        actor_id=request.user.pk,
                        notify_consultant=True,
                        metadata=metadata,
                    )
                else:  # pragma: no cover - safeguard against unsupported status values
                    missing += 1
                    continue
            except Exception:
                messages.error(
                    request,
                    "Failed to queue the certificate update task. Please try again.",
                )
                continue

            applied += 1

        if applied:
            message = ngettext(
                "Successfully updated %(count)d certificate.",
                "Successfully updated %(count)d certificates.",
                applied,
            ) % {"count": applied}
            self.message_user(request, message, level=messages.SUCCESS)
        if missing:
            warning_message = ngettext(
                "%(count)d consultant had no certificate to update.",
                "%(count)d consultants had no certificate to update.",
                missing,
            ) % {"count": missing}
            self.message_user(request, warning_message, level=messages.WARNING)

        return None


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
