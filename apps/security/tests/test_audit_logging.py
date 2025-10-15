from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.certificates.services import generate_approval_certificate, generate_rejection_letter
from apps.consultants.models import Consultant, Notification
from apps.security.models import AuditLog


class AuditLogIntegrationTests(TestCase):
    password = "changeme123"

    def setUp(self):
        super().setUp()
        self.user_model = get_user_model()
        self.staff_group, _ = Group.objects.get_or_create(name="Staff")
        self.staff_user = self.user_model.objects.create_user(
            username="audit-staff",
            password=self.password,
            email="audit-staff@example.com",
        )
        self.staff_user.groups.add(self.staff_group)
        self.client.login(username=self.staff_user.username, password=self.password)

    def _create_consultant(self, status: str = "submitted") -> Consultant:
        applicant = self.user_model.objects.create_user(
            username=f"consultant-{status}",
            password="applicantpass123",
            email=f"consultant-{status}@example.com",
        )
        return Consultant.objects.create(
            user=applicant,
            full_name="Audit Target",
            id_number="AUD-001",
            dob=date(1990, 1, 1),
            gender="M",
            nationality="Testland",
            email=applicant.email,
            phone_number="1234567890",
            business_name="Audit Business",
            status=status,
        )

    def test_status_change_creates_enriched_audit_log(self):
        consultant = self._create_consultant(status="submitted")

        response = self.client.post(
            reverse("staff_dashboard"),
            {"consultant_id": consultant.pk, "action": "approved"},
            HTTP_X_FORWARDED_FOR="203.0.113.10",
        )
        self.assertEqual(response.status_code, 302)

        log = AuditLog.objects.filter(action_code=AuditLog.ActionCode.APPROVE_APPLICATION).latest(
            "timestamp"
        )
        self.assertEqual(log.user, self.staff_user)
        self.assertEqual(log.resolved_role, "staff")
        self.assertEqual(log.endpoint, reverse("staff_dashboard"))
        self.assertEqual(str(log.client_ip), "203.0.113.10")
        self.assertEqual(log.target, f"Consultant:{consultant.pk}")
        self.assertEqual(log.context["new_status"], "approved")
        self.assertEqual(log.context["previous_status"], "submitted")

        notification = Notification.objects.get(recipient=consultant.user)
        self.assertEqual(notification.audit_log, log)

    def test_certificate_generation_emits_audit_event(self):
        consultant = self._create_consultant(status="approved")

        generate_approval_certificate(
            consultant,
            generated_by="Review Er",
            actor=self.staff_user,
        )

        log = AuditLog.objects.filter(action_code=AuditLog.ActionCode.CERTIFICATE_ISSUED).latest(
            "timestamp"
        )
        self.assertEqual(log.user, self.staff_user)
        self.assertEqual(log.resolved_role, "staff")
        self.assertEqual(log.target, f"Consultant:{consultant.pk}")
        self.assertEqual(
            log.endpoint,
            "apps.certificates.services.generate_approval_certificate",
        )
        self.assertEqual(log.context.get("consultant_id"), consultant.pk)
        self.assertEqual(log.context.get("generated_by"), "Review Er")
        self.assertIsNotNone(log.context.get("certificate_id"))

    def test_certificate_revocation_emits_audit_event(self):
        consultant = self._create_consultant(status="approved")
        generate_approval_certificate(consultant, generated_by="Review Er", actor=self.staff_user)

        generate_rejection_letter(
            consultant,
            generated_by="Review Er",
            actor=self.staff_user,
        )

        log = AuditLog.objects.filter(action_code=AuditLog.ActionCode.CERTIFICATE_REVOKED).latest(
            "timestamp"
        )
        self.assertEqual(log.user, self.staff_user)
        self.assertEqual(log.resolved_role, "staff")
        self.assertEqual(log.target, f"Consultant:{consultant.pk}")
        self.assertEqual(
            log.endpoint,
            "apps.certificates.services.generate_rejection_letter",
        )
        self.assertEqual(log.context.get("consultant_id"), consultant.pk)


class AdminAuditDashboardTests(TestCase):
    password = "supersafe123"

    def setUp(self):
        super().setUp()
        self.user_model = get_user_model()
        self.superuser = self.user_model.objects.create_superuser(
            username="audit-admin",
            password=self.password,
            email="audit-admin@example.com",
        )
        self.staff_group, _ = Group.objects.get_or_create(name="Staff")

    def test_superuser_can_view_audit_dashboard(self):
        staff_member = self.user_model.objects.create_user(
            username="staff-member",
            password="tmp-pass-123",
            email="staff-member@example.com",
        )
        staff_member.groups.add(self.staff_group)
        AuditLog.objects.create(
            user=staff_member,
            resolved_role="staff",
            action_code=AuditLog.ActionCode.VIEW_CONSULTANT,
            target="Consultant:1",
            endpoint="/staff-dashboard/",
            client_ip="127.0.0.1",
            context={"consultant_id": 1},
        )

        self.client.login(username=self.superuser.username, password=self.password)
        response = self.client.get(reverse("admin_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Audit log")
        self.assertContains(response, "Client IP")
        self.assertContains(response, "Consultant:1")

    def test_non_superuser_cannot_view_audit_dashboard(self):
        staff_user = self.user_model.objects.create_user(
            username="regular-staff",
            password=self.password,
            email="regular-staff@example.com",
        )
        staff_user.groups.add(self.staff_group)
        self.client.login(username=staff_user.username, password=self.password)

        url = reverse("admin_dashboard")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("forbidden")))

    @override_settings(ADMIN_REPORT_RECIPIENTS=("board@example.com",))
    def test_manual_report_send_creates_audit_log_and_email(self):
        applicant = self.user_model.objects.create_user(
            username="manual-report",
            password="pass-12345",
            email="manual-report@example.com",
        )
        Consultant.objects.create(
            user=applicant,
            full_name="Manual Report",
            id_number="MR-001",
            dob=date(1990, 1, 1),
            gender="F",
            nationality="Testland",
            email=applicant.email,
            phone_number="0712345678",
            business_name="Manual Co",
            status="submitted",
            submitted_at=timezone.now(),
            consultant_type="General",
        )

        self.client.login(username=self.superuser.username, password=self.password)
        mail.outbox = []

        response = self.client.post(reverse("admin_dashboard_send_report"))

        self.assertRedirects(response, reverse("admin_dashboard"))
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["board@example.com"])
        self.assertTrue(message.attachments)

        log = AuditLog.objects.filter(
            action_code=AuditLog.ActionCode.SEND_ANALYTICS_REPORT
        ).latest("timestamp")
        self.assertEqual(log.user, self.superuser)
        self.assertEqual(log.resolved_role, "admin")
        self.assertEqual(log.target, "AdminReport")
        self.assertEqual(log.endpoint, reverse("admin_dashboard_send_report"))
        self.assertEqual(log.context.get("status"), "sent")
        self.assertEqual(log.context.get("report_type"), "manual")
        self.assertEqual(log.context.get("recipient_count"), 1)


class AuditLogAuthenticationTests(TestCase):
    password = "changeme123"

    def setUp(self):
        super().setUp()
        self.user_model = get_user_model()
        self.staff_group, _ = Group.objects.get_or_create(name="Staff")
        self.staff_user = self.user_model.objects.create_user(
            username="login-staff",
            password=self.password,
            email="login-staff@example.com",
        )
        self.staff_user.groups.add(self.staff_group)

    def test_login_success_logs_metadata(self):
        response = self.client.post(
            reverse("login"),
            {"username": self.staff_user.username, "password": self.password},
            HTTP_X_FORWARDED_FOR="198.51.100.20",
        )
        self.assertEqual(response.status_code, 302)

        log = AuditLog.objects.filter(action_code=AuditLog.ActionCode.LOGIN_SUCCESS).latest(
            "timestamp"
        )
        self.assertEqual(log.user, self.staff_user)
        self.assertEqual(log.resolved_role, "staff")
        self.assertEqual(log.endpoint, reverse("login"))
        self.assertEqual(str(log.client_ip), "198.51.100.20")
        self.assertEqual(log.context.get("username"), self.staff_user.username)

    def test_login_failure_logs_metadata(self):
        response = self.client.post(
            reverse("login"),
            {"username": self.staff_user.username, "password": "incorrect"},
            REMOTE_ADDR="192.0.2.44",
        )
        self.assertEqual(response.status_code, 200)

        log = AuditLog.objects.filter(action_code=AuditLog.ActionCode.LOGIN_FAILURE).latest(
            "timestamp"
        )
        self.assertIsNone(log.user)
        self.assertEqual(log.resolved_role, "anonymous")
        self.assertEqual(log.endpoint, reverse("login"))
        self.assertEqual(str(log.client_ip), "192.0.2.44")
        self.assertEqual(log.context.get("username"), self.staff_user.username)
        self.assertIn("non_field_errors", log.context.get("errors", {}))
