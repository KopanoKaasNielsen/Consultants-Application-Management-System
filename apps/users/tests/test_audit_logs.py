from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from apps.consultants.models import Consultant
from apps.users.models import AuditLog


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

    def _create_consultant(self, status="submitted"):
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

    def test_status_change_creates_audit_log_entry(self):
        consultant = self._create_consultant(status="submitted")

        response = self.client.post(
            reverse("staff_dashboard"),
            {"consultant_id": consultant.pk, "action": "approved"},
        )
        self.assertEqual(response.status_code, 302)

        log = AuditLog.objects.get()
        self.assertEqual(log.action_type, AuditLog.ActionType.APPROVE_APPLICATION)
        self.assertEqual(log.metadata["new_status"], "approved")
        self.assertEqual(log.metadata["previous_status"], "submitted")
        self.assertEqual(log.metadata["consultant_id"], consultant.pk)

    def test_consultant_detail_view_is_logged(self):
        consultant = self._create_consultant(status="approved")

        response = self.client.get(reverse("staff_consultant_detail", args=[consultant.pk]))
        self.assertEqual(response.status_code, 200)

        log = AuditLog.objects.get()
        self.assertEqual(log.action_type, AuditLog.ActionType.VIEW_CONSULTANT)
        self.assertEqual(log.metadata["consultant_id"], consultant.pk)


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
        AuditLog.objects.create(
            user=staff_member,
            action_type=AuditLog.ActionType.VIEW_CONSULTANT,
            target_object="Consultant:1",
            metadata={"consultant_id": 1},
        )

        self.client.login(username=self.superuser.username, password=self.password)
        response = self.client.get(reverse("admin_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Audit log")
        self.assertContains(response, "Consultant:1")

    def test_non_superuser_cannot_view_audit_dashboard(self):
        staff_user = self.user_model.objects.create_user(
            username="regular-staff",
            password=self.password,
            email="regular-staff@example.com",
        )
        staff_user.groups.add(self.staff_group)
        self.client.login(username=staff_user.username, password=self.password)

        response = self.client.get(reverse("admin_dashboard"))

        self.assertEqual(response.status_code, 403)
