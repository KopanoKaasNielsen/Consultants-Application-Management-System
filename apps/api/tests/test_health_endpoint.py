"""Tests for the API health summary endpoint."""

from __future__ import annotations

from datetime import timedelta

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.security.models import AuditLog


class HealthEndpointTests(TestCase):
    """Verify the /api/health/ endpoint reports core signals."""

    def test_health_endpoint_returns_status_payload(self):
        url = reverse("api:health-summary")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("status", payload)
        self.assertIn("timestamp", payload)
        self.assertIn("database", payload)
        self.assertIn("recent_critical_events", payload)

    @override_settings(SECURITY_ALERT_LOGIN_FAILURE_THRESHOLD=2)
    def test_recent_critical_events_counts_alerts(self):
        now = timezone.now()

        failure_log = AuditLog.objects.create(
            action_code=AuditLog.ActionCode.LOGIN_FAILURE,
            context={"failure_count": 3},
        )
        failure_log.timestamp = now - timedelta(minutes=5)
        failure_log.save(update_fields=["timestamp"])

        success_log = AuditLog.objects.create(
            action_code=AuditLog.ActionCode.LOGIN_SUCCESS,
            context={"severity": "info"},
        )
        success_log.timestamp = now - timedelta(minutes=5)
        success_log.save(update_fields=["timestamp"])

        url = reverse("api:health-summary")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        payload = response.json()
        self.assertGreaterEqual(payload["recent_critical_events"], 1)
