from __future__ import annotations

import json
from io import StringIO

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.security.models import AuditLog


pytestmark = pytest.mark.django_db


class ExportAuditLogsCommandTests(TestCase):
    def setUp(self):
        super().setUp()
        self.assertIn("rest_framework", settings.INSTALLED_APPS)
        self.user = get_user_model().objects.create_user(
            username="log-user",
            email="log-user@example.com",
            password="password123",
            first_name="Log",
            last_name="User",
        )
        AuditLog.objects.create(
            user=self.user,
            resolved_role="staff",
            action_code=AuditLog.ActionCode.LOGIN_SUCCESS,
            target="/login/",
            endpoint="/login/",
            client_ip="192.0.2.10",
            context={"detail": "Successful login"},
            timestamp=timezone.now(),
        )
        AuditLog.objects.create(
            user=None,
            resolved_role="",
            action_code=AuditLog.ActionCode.LOGIN_FAILURE,
            target="/login/",
            endpoint="/login/",
            context={"detail": "Invalid password"},
            timestamp=timezone.now(),
        )

    def test_exports_markdown_without_sensitive_fields_by_default(self):
        output = StringIO()
        call_command("export_audit_logs", limit=2, stdout=output)
        rendered = output.getvalue()

        self.assertIn("| Timestamp | Actor | Role | Action | Target | Endpoint | Context |", rendered)
        self.assertIn("Successful login", rendered)
        self.assertNotIn("192.0.2.10", rendered)
        self.assertNotIn("log-user@example.com", rendered)
        self.assertIn("Log User", rendered)
        self.assertIn("anonymous", rendered)

    def test_json_format_and_optional_fields(self):
        output = StringIO()
        call_command(
            "export_audit_logs",
            limit=2,
            format="json",
            include_ip=True,
            include_contact_details=True,
            stdout=output,
        )
        payload = json.loads(output.getvalue())

        self.assertEqual(len(payload), 2)
        self.assertTrue(all("timestamp" in row for row in payload))
        actor_entry = next(row for row in payload if row["actor"].startswith("Log User"))
        self.assertEqual(actor_entry["client_ip"], "192.0.2.10")
        self.assertIn("log-user@example.com", actor_entry["actor"])
