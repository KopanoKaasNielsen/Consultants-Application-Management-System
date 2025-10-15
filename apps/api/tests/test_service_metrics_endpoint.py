"""Tests for the service metrics aggregation endpoint."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.security.models import AuditLog


class ServiceMetricsEndpointTests(TestCase):
    """Validate the behaviour of the /api/metrics/ endpoint."""

    def setUp(self):
        self.url = reverse("api:service-metrics")
        self.superuser = get_user_model().objects.create_superuser(
            username="metrics-admin",
            email="metrics@example.com",
            password="test-password",
        )

    def test_superuser_receives_metrics_payload(self):
        now = timezone.now()

        primary_log = AuditLog.objects.create(
            user=self.superuser,
            action_code=AuditLog.ActionCode.LOGIN_SUCCESS,
            endpoint="/api/example/",
            context={"response_time_ms": 120},
        )
        primary_log.timestamp = now - timedelta(seconds=30)
        primary_log.save(update_fields=["timestamp"])

        slow_log = AuditLog.objects.create(
            user=self.superuser,
            action_code=AuditLog.ActionCode.LOGIN_SUCCESS,
            endpoint="/api/example/",
            context={"response_time_ms": 240},
        )
        slow_log.timestamp = now - timedelta(minutes=5)
        slow_log.save(update_fields=["timestamp"])

        alert_log = AuditLog.objects.create(
            user=self.superuser,
            action_code=AuditLog.ActionCode.LOGIN_FAILURE,
            endpoint="/api/auth/login/",
            context={"severity": "critical", "alert_active": True},
        )
        alert_log.timestamp = now - timedelta(minutes=10)
        alert_log.save(update_fields=["timestamp"])

        celery_metrics = {
            "status": "healthy",
            "worker_count": 2,
            "queue_length": 5,
            "active_tasks": 4,
            "scheduled_tasks": 1,
        }

        with patch("apps.api.views._collect_celery_metrics", return_value=celery_metrics), patch(
            "apps.api.views._collect_throttle_metrics",
            return_value={
                "scope": "role",
                "role_rates": {"admin": "60/min"},
                "per_role_limits": {"admin": {"requests": 60, "window_seconds": 60}},
                "max_window_seconds": 60,
            },
        ):
            self.client.force_login(self.superuser)
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertIn("request_throughput_per_minute", payload)
        self.assertGreaterEqual(payload["request_throughput_per_minute"], 1)
        self.assertAlmostEqual(payload["average_response_time_ms"], 180.0)
        self.assertEqual(payload["recent_errors"], 1)
        self.assertEqual(payload["celery"], celery_metrics)
        self.assertEqual(payload["throttle"]["scope"], "role")
        self.assertTrue(any(item["endpoint"] == "/api/example/" for item in payload["top_endpoints"]))
        self.assertTrue(payload["active_alerts"])

    def test_non_admin_user_is_forbidden(self):
        user = get_user_model().objects.create_user(
            username="metrics-staff",
            email="staff@example.com",
            password="test-password",
        )
        self.client.force_login(user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)
