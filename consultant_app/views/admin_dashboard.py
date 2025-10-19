"""Views powering the staff-facing admin dashboard."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Dict

from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.paginator import Paginator
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.dateparse import parse_date
from django.views.generic import TemplateView

from apps.security.models import AuditLog
from apps.users.constants import UserRole
from apps.users.permissions import user_has_role
from consultant_app.utils.admin_dashboard import compute_admin_dashboard_stats


@dataclass
class AuditLogFilters:
    """Structured representation of the audit log filters."""

    action_type: str = ""
    user: str = ""
    start: str = ""
    end: str = ""


class AdminDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """Render the analytics-rich admin dashboard for staff and superusers."""

    template_name = "consultant_app/admin_dashboard.html"
    paginate_by = 25
    login_url = "login"

    def test_func(self) -> bool:
        user = self.request.user
        return bool(getattr(user, "is_active", False) and getattr(user, "is_staff", False))

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            forbidden_url = f"{reverse('forbidden')}?next={self.request.get_full_path()}"
            return redirect(forbidden_url)
        return super().handle_no_permission()

    def get_filters(self) -> AuditLogFilters:
        request = self.request
        return AuditLogFilters(
            action_type=(request.GET.get("action_type") or "").strip(),
            user=(request.GET.get("user") or "").strip(),
            start=(request.GET.get("start") or "").strip(),
            end=(request.GET.get("end") or "").strip(),
        )

    def get_filtered_logs(self, filters: AuditLogFilters):
        logs = AuditLog.objects.select_related("user")

        if filters.action_type:
            logs = logs.filter(action_code=filters.action_type)
        if filters.user:
            logs = logs.filter(user_id=filters.user)
        if filters.start:
            parsed_start = parse_date(filters.start)
            if parsed_start:
                logs = logs.filter(timestamp__date__gte=parsed_start)
        if filters.end:
            parsed_end = parse_date(filters.end)
            if parsed_end:
                logs = logs.filter(timestamp__date__lte=parsed_end)

        return logs

    def _serialise_log_context(self, page_obj) -> None:
        for entry in page_obj.object_list:
            try:
                entry.context_pretty = json.dumps(entry.context, indent=2, sort_keys=True)
            except TypeError:
                entry.context_pretty = str(entry.context)

    def get_filter_payload(self, filters: AuditLogFilters) -> Dict[str, str]:
        return {
            "action_type": filters.action_type,
            "user": filters.user,
            "start": filters.start,
            "end": filters.end,
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        filters = self.get_filters()
        logs = self.get_filtered_logs(filters)
        paginator = Paginator(logs, self.paginate_by)
        page_obj = paginator.get_page(self.request.GET.get("page"))
        self._serialise_log_context(page_obj)

        user_model = get_user_model()
        active_users = user_model.objects.filter(is_active=True).order_by("username")
        stats = compute_admin_dashboard_stats()
        stats_json = json.dumps(stats, default=str)

        context.update(
            {
                "page_obj": page_obj,
                "paginator": paginator,
                "logs": page_obj.object_list,
                "filters": self.get_filter_payload(filters),
                "action_choices": AuditLog.ActionCode.choices,
                "users": active_users,
                "stats": stats,
                "stats_json": stats_json,
                "stats_endpoint": reverse("api:admin-stats"),
                "can_send_manual_report": user_has_role(
                    self.request.user, UserRole.ADMIN
                ),
            }
        )

        return context


__all__ = ["AdminDashboardView"]
