from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.consultants.models import Consultant
from apps.decisions.models import ApplicationAction
from apps.decisions.views import ACTION_MESSAGES
from apps.users.constants import (
    BACKOFFICE_GROUP_NAME,
    BOARD_COMMITTEE_GROUP_NAME,
    CONSULTANTS_GROUP_NAME,
)


class DecisionsViewTests(TestCase):
    """Integration-style tests covering reviewer views and actions."""

    def setUp(self):
        super().setUp()
        call_command("seed_groups")
        self.user_model = get_user_model()
        self.board_user = self._create_user(
            "board_member", [BOARD_COMMITTEE_GROUP_NAME]
        )
        self.staff_user = self._create_user("staff_member", [BACKOFFICE_GROUP_NAME])
        self.non_reviewer = self._create_user(
            "consultant_user", [CONSULTANTS_GROUP_NAME]
        )
        # Baseline consultants for listing/detail views
        self.list_consultants = {
            "draft": self._create_consultant("Draft Applicant", "draft", None),
            "submitted": self._create_consultant(
                "Submitted Applicant", "submitted", timezone.now()
            ),
            "vetted": self._create_consultant(
                "Vetted Applicant", "vetted", timezone.now() - timedelta(days=1)
            ),
            "approved": self._create_consultant(
                "Approved Applicant", "approved", timezone.now() - timedelta(days=2)
            ),
            "rejected": self._create_consultant(
                "Rejected Applicant", "rejected", timezone.now() - timedelta(days=3)
            ),
        }

    def _create_user(self, username, groups):
        user = self.user_model.objects.create_user(
            username=username,
            email=f"{username}@example.com",
            password="password123",
        )
        if groups:
            group_objs = Group.objects.filter(name__in=groups)
            user.groups.set(group_objs)
        return user

    def _create_consultant(self, name, status, submitted_at):
        user = self.user_model.objects.create_user(
            username=f"{name.lower().replace(' ', '_')}",
            email=f"{name.lower().replace(' ', '.')}@example.com",
            password="password123",
        )
        consultant = Consultant.objects.create(
            user=user,
            full_name=name,
            id_number="ID123456",
            dob=date(1990, 1, 1),
            gender="M",
            nationality="Testland",
            email=user.email,
            phone_number="123456789",
            business_name="Test Business",
            registration_number="REG-001",
            submitted_at=submitted_at,
            status=status,
        )
        return consultant

    def test_decisions_dashboard_access_control(self):
        url = reverse("decisions_dashboard")

        self.client.force_login(self.board_user)
        self.assertEqual(self.client.get(url).status_code, 200)

        self.client.force_login(self.staff_user)
        self.assertEqual(self.client.get(url).status_code, 200)

        self.client.force_login(self.non_reviewer)
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_applications_list_access_control(self):
        url = reverse("officer_applications_list")

        self.client.force_login(self.board_user)
        self.assertEqual(self.client.get(url).status_code, 200)

        self.client.force_login(self.staff_user)
        self.assertEqual(self.client.get(url).status_code, 200)

        self.client.force_login(self.non_reviewer)
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_application_detail_access_control(self):
        detail_target = self.list_consultants["submitted"]
        url = reverse("officer_application_detail", args=[detail_target.pk])

        self.client.force_login(self.board_user)
        self.assertEqual(self.client.get(url).status_code, 200)

        self.client.force_login(self.staff_user)
        self.assertEqual(self.client.get(url).status_code, 200)

        self.client.force_login(self.non_reviewer)
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_applications_list_default_status_filter(self):
        url = reverse("officer_applications_list")
        self.client.force_login(self.staff_user)
        response = self.client.get(url)

        applications = list(response.context["applications"])
        self.assertSetEqual(
            {app.full_name for app in applications},
            {"Submitted Applicant", "Vetted Applicant"},
        )
        self.assertEqual(response.context["active_status"], "submitted,vetted")

    def test_applications_list_explicit_status_filter(self):
        url = reverse("officer_applications_list")
        self.client.force_login(self.staff_user)

        response = self.client.get(url, {"status": "approved"})
        applications = list(response.context["applications"])
        self.assertEqual([app.full_name for app in applications], ["Approved Applicant"])
        self.assertEqual(response.context["active_status"], "approved")

        response = self.client.get(url, {"status": "rejected"})
        applications = list(response.context["applications"])
        self.assertEqual([app.full_name for app in applications], ["Rejected Applicant"])
        self.assertEqual(response.context["active_status"], "rejected")

    @patch("apps.decisions.views.send_decision_email")
    @patch("apps.decisions.views.generate_rejection_letter")
    @patch("apps.decisions.views.generate_approval_certificate")
    def test_decisions_dashboard_actions(
        self,
        mock_generate_certificate,
        mock_generate_rejection,
        mock_send_email,
    ):
        self.client.force_login(self.staff_user)
        url = reverse("decisions_dashboard")

        scenarios = {
            "vetted": {
                "initial_status": "submitted",
                "expected_status": "vetted",
                "email_called": False,
                "certificate_called": False,
                "rejection_called": False,
            },
            "approved": {
                "initial_status": "vetted",
                "expected_status": "approved",
                "email_called": True,
                "certificate_called": True,
                "rejection_called": False,
            },
            "rejected": {
                "initial_status": "vetted",
                "expected_status": "rejected",
                "email_called": True,
                "certificate_called": False,
                "rejection_called": True,
            },
        }

        for action, expectations in scenarios.items():
            with self.subTest(action=action):
                consultant = self._create_consultant(
                    f"Dashboard {action}",
                    expectations["initial_status"],
                    timezone.now(),
                )

                mock_send_email.reset_mock()
                mock_generate_certificate.reset_mock()
                mock_generate_rejection.reset_mock()

                response = self.client.post(
                    url,
                    {
                        "consultant_id": consultant.pk,
                        "action": action,
                        "notes": f"Notes for {action}",
                    },
                    follow=True,
                )

                self.assertRedirects(response, url)
                consultant.refresh_from_db()
                self.assertEqual(consultant.status, expectations["expected_status"])

                messages = list(response.context["messages"])
                self.assertTrue(messages)
                self.assertEqual(messages[0].message, ACTION_MESSAGES[action])

                self.assertEqual(mock_send_email.called, expectations["email_called"])
                self.assertEqual(
                    mock_generate_certificate.called,
                    expectations["certificate_called"],
                )
                self.assertEqual(
                    mock_generate_rejection.called, expectations["rejection_called"]
                )

                action_record = ApplicationAction.objects.get(consultant=consultant)
                self.assertEqual(action_record.action, action)

    @patch("apps.decisions.views.send_decision_email")
    @patch("apps.decisions.views.generate_rejection_letter")
    @patch("apps.decisions.views.generate_approval_certificate")
    def test_application_detail_actions(
        self,
        mock_generate_certificate,
        mock_generate_rejection,
        mock_send_email,
    ):
        self.client.force_login(self.board_user)

        scenarios = {
            "vetted": {
                "expected_status": "vetted",
                "email_called": False,
                "certificate_called": False,
                "rejection_called": False,
            },
            "approved": {
                "expected_status": "approved",
                "email_called": True,
                "certificate_called": True,
                "rejection_called": False,
            },
            "rejected": {
                "expected_status": "rejected",
                "email_called": True,
                "certificate_called": False,
                "rejection_called": True,
            },
        }

        for action, expectations in scenarios.items():
            with self.subTest(action=action):
                consultant = self._create_consultant(
                    f"Detail {action}",
                    "submitted",
                    timezone.now(),
                )
                detail_url = reverse(
                    "officer_application_detail", args=[consultant.pk]
                )

                mock_send_email.reset_mock()
                mock_generate_certificate.reset_mock()
                mock_generate_rejection.reset_mock()

                response = self.client.post(
                    detail_url,
                    {
                        "action": action,
                        "notes": f"Detail {action} notes",
                    },
                    follow=True,
                )

                self.assertRedirects(response, detail_url)
                consultant.refresh_from_db()
                self.assertEqual(consultant.status, expectations["expected_status"])

                messages = list(response.context["messages"])
                self.assertTrue(messages)
                self.assertEqual(messages[0].message, ACTION_MESSAGES[action])

                self.assertEqual(mock_send_email.called, expectations["email_called"])
                self.assertEqual(
                    mock_generate_certificate.called,
                    expectations["certificate_called"],
                )
                self.assertEqual(
                    mock_generate_rejection.called, expectations["rejection_called"]
                )

                action_record = ApplicationAction.objects.get(consultant=consultant)
                self.assertEqual(action_record.action, action)
