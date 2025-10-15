"""Tests for alerting and monitoring integrations."""

from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.db.models.signals import post_save
from django.test import TestCase, override_settings

from apps.security.models import AuditLog
from apps.security.tasks import send_audit_log_alert
from utils.alert_notifier import AlertMessage, send_security_alert
from apps.security import signals as security_signals


class SecurityAlertSignalTests(TestCase):
    """Ensure critical audit log entries trigger alerts."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="alice",
            email="alice@example.com",
            password="password123",
        )

    @override_settings(
        SECURITY_ALERT_EMAIL_RECIPIENTS=("secops@example.com",),
        SECURITY_ALERT_SLACK_WEBHOOK="https://hooks.slack.com/services/test",
    )
    @patch("apps.security.signals.send_audit_log_alert.delay")
    def test_critical_severity_context_triggers_alert(self, mock_delay):
        log = AuditLog.objects.create(
            user=self.user,
            action_code=AuditLog.ActionCode.LOGIN_SUCCESS,
            endpoint="/login/",
            context={"severity": "critical"},
        )

        mock_delay.assert_called_once_with(log.pk)

    @override_settings(SECURITY_ALERT_LOGIN_FAILURE_THRESHOLD=3)
    @patch("apps.security.signals.send_audit_log_alert.delay")
    def test_login_failure_threshold_triggers_alert(self, mock_delay):
        log = AuditLog.objects.create(
            user=self.user,
            action_code=AuditLog.ActionCode.LOGIN_FAILURE,
            endpoint="/login/",
            context={"failure_count": 3},
        )

        mock_delay.assert_called_once_with(log.pk)

    @override_settings(SECURITY_ALERT_CRITICAL_ACTIONS={"certificate_revoked"})
    @patch("apps.security.signals.send_audit_log_alert.delay")
    def test_certificate_revocation_triggers_alert(self, mock_delay):
        log = AuditLog.objects.create(
            user=self.user,
            action_code=AuditLog.ActionCode.CERTIFICATE_REVOKED,
            target="cert-123",
            context={},
        )

        mock_delay.assert_called_once_with(log.pk)

    @patch("apps.security.signals.send_audit_log_alert.delay")
    def test_low_severity_does_not_trigger_alert(self, mock_delay):
        AuditLog.objects.create(
            user=self.user,
            action_code=AuditLog.ActionCode.LOGIN_SUCCESS,
            endpoint="/dashboard/",
            context={"severity": "info"},
        )

        mock_delay.assert_not_called()


class AlertNotifierTests(TestCase):
    """Validate alert notification delivery helpers."""

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        SECURITY_ALERT_EMAIL_RECIPIENTS=("secops@example.com",),
        SECURITY_ALERT_EMAIL_SENDER="alerts@example.com",
        SECURITY_ALERT_EMAIL_SUBJECT_PREFIX="Monitoring",
        SECURITY_ALERT_SLACK_WEBHOOK="https://hooks.slack.com/services/test",
    )
    @patch("utils.alert_notifier.urlopen")
    def test_send_security_alert_dispatches_to_channels(self, mock_urlopen):
        response = mock_urlopen.return_value.__enter__.return_value
        response.read.return_value = b"ok"

        alert = AlertMessage(
            title="Repeated login failures detected",
            body="Multiple failed login attempts recorded for admin@example.com",
            severity="critical",
            metadata={"user": "admin@example.com", "failure_count": 6},
        )

        send_security_alert(alert)

        mock_urlopen.assert_called_once()
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertIn("[Monitoring][CRITICAL]", message.subject)
        self.assertIn("Repeated login failures", message.subject)
        self.assertIn("Details:", message.body)
        self.assertIn("failure_count: 6", message.body)
        self.assertIn("user: admin@example.com", message.body)


class AuditLogTaskTests(TestCase):
    """Ensure Celery tasks build detailed alert messages."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="bob",
            email="bob@example.com",
            password="password123",
        )

    @override_settings(SECURITY_ALERT_CRITICAL_ACTIONS={"certificate_revoked"})
    @patch("apps.security.tasks.send_security_alert")
    def test_send_audit_log_alert_includes_metadata(self, mock_send_alert):
        post_save.disconnect(security_signals.trigger_critical_alert, sender=AuditLog)
        self.addCleanup(
            post_save.connect,
            security_signals.trigger_critical_alert,
            sender=AuditLog,
        )

        log = AuditLog.objects.create(
            user=self.user,
            action_code=AuditLog.ActionCode.CERTIFICATE_REVOKED,
            target="cert-789",
            endpoint="/api/certificates/",
            client_ip="127.0.0.1",
            context={"severity": "critical", "reason": "manual"},
        )

        send_audit_log_alert.run(log.pk)

        mock_send_alert.assert_called_once()
        alert = mock_send_alert.call_args[0][0]
        self.assertIsInstance(alert, AlertMessage)
        self.assertIn("Critical security event", alert.title)
        self.assertEqual(alert.metadata["action"], "Revoked consultant certificate")
        self.assertEqual(alert.metadata["client_ip"], "127.0.0.1")
        self.assertEqual(alert.metadata["target"], "cert-789")
        self.assertEqual(alert.severity, "critical")
