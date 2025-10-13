from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.certificates.models import CertificateRenewal
from apps.consultants.models import Consultant
from apps.decisions.models import ApplicationAction
from apps.decisions.views import ACTION_MESSAGES
from apps.users.constants import (
    BACKOFFICE_GROUP_NAME,
    BOARD_COMMITTEE_GROUP_NAME,
    CONSULTANTS_GROUP_NAME,
)
from consultant_app.models import Certificate


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

    def _issue_certificate(self, consultant, *, issued_days_ago=200, valid_for_days=365):
        issued_at = timezone.now() - timedelta(days=issued_days_ago)
        consultant.certificate_generated_at = issued_at
        consultant.certificate_expires_at = issued_at.date() + timedelta(days=valid_for_days)
        consultant.certificate_pdf = SimpleUploadedFile(
            "approval.pdf", b"certificate", content_type="application/pdf"
        )
        consultant.save(
            update_fields=[
                "certificate_pdf",
                "certificate_generated_at",
                "certificate_expires_at",
            ]
        )
        Certificate.objects.create(
            consultant=consultant,
            status=Certificate.Status.VALID,
            issued_at=issued_at,
            status_set_at=issued_at,
            valid_at=issued_at,
        )
        consultant.refresh_from_db()
        return consultant

    def test_decisions_dashboard_access_control(self):
        url = reverse("decisions_dashboard")

        self.client.force_login(self.board_user)
        self.assertEqual(self.client.get(url).status_code, 200)

        self.client.force_login(self.staff_user)
        self.assertEqual(self.client.get(url).status_code, 200)

        self.client.force_login(self.non_reviewer)
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_decisions_dashboard_lists_pending_applications(self):
        url = reverse("decisions_dashboard")

        self.client.force_login(self.board_user)
        response = self.client.get(url)

        consultants = list(response.context["consultants"])
        self.assertEqual(
            [consultant.full_name for consultant in consultants],
            ["Submitted Applicant", "Vetted Applicant"],
        )
        self.assertTrue(
            all(consultant.status in {"submitted", "vetted"} for consultant in consultants)
        )

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

    @patch("apps.decisions.services.transaction.on_commit")
    @patch("apps.decisions.services.generate_rejection_letter_task.delay")
    @patch("apps.decisions.services.generate_approval_certificate_task.delay")
    def test_decisions_dashboard_actions(
        self,
        mock_generate_certificate,
        mock_generate_rejection,
        mock_on_commit,
    ):
        self.client.force_login(self.staff_user)
        url = reverse("decisions_dashboard")

        mock_on_commit.side_effect = lambda func, using=None: func()

        scenarios = {
            "vetted": {
                "initial_status": "submitted",
                "expected_status": "vetted",
            },
            "approved": {
                "initial_status": "vetted",
                "expected_status": "approved",
            },
            "rejected": {
                "initial_status": "vetted",
                "expected_status": "rejected",
            },
        }

        for action, expectations in scenarios.items():
            with self.subTest(action=action):
                consultant = self._create_consultant(
                    f"Dashboard {action}",
                    expectations["initial_status"],
                    timezone.now(),
                )

                mock_generate_certificate.reset_mock()
                mock_generate_rejection.reset_mock()
                mock_on_commit.reset_mock()
                mock_on_commit.side_effect = lambda func, using=None: func()

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

                mock_on_commit.assert_called_once()
                generated_by = self.staff_user.get_full_name() or self.staff_user.username
                if action == "approved":
                    mock_generate_certificate.assert_called_once_with(
                        consultant.pk, generated_by
                    )
                    mock_generate_rejection.assert_not_called()
                elif action == "rejected":
                    mock_generate_rejection.assert_called_once_with(
                        consultant.pk, generated_by
                    )
                    mock_generate_certificate.assert_not_called()
                else:
                    mock_generate_certificate.assert_not_called()
                    mock_generate_rejection.assert_not_called()

                action_record = ApplicationAction.objects.get(consultant=consultant)
                self.assertEqual(action_record.action, action)

    def test_renewal_requests_access_control(self):
        url = reverse("certificate_renewal_requests")

        self.client.force_login(self.board_user)
        self.assertEqual(self.client.get(url).status_code, 200)

        self.client.force_login(self.staff_user)
        self.assertEqual(self.client.get(url).status_code, 200)

        self.client.force_login(self.non_reviewer)
        self.assertEqual(self.client.get(url).status_code, 403)

    @patch("apps.decisions.views.transaction.on_commit")
    @patch("apps.decisions.tasks.generate_approval_certificate_task.delay")
    def test_reviewer_can_approve_renewal(
        self, mock_generate_certificate, mock_on_commit
    ):
        consultant = self._create_consultant("Renewal Applicant", "approved", timezone.now())
        consultant = self._issue_certificate(consultant, issued_days_ago=360)
        renewal = CertificateRenewal.objects.create(consultant=consultant)

        mock_on_commit.side_effect = lambda func, using=None: func()

        url = reverse("certificate_renewal_requests")
        self.client.force_login(self.staff_user)

        response = self.client.post(
            url,
            {
                "renewal_id": renewal.pk,
                "decision": "approve",
                "notes": "All good",
            },
            follow=True,
        )

        self.assertRedirects(response, url)
        renewal.refresh_from_db()
        self.assertEqual(renewal.status, CertificateRenewal.Status.APPROVED)
        mock_generate_certificate.assert_called_once_with(
            consultant.pk, self.staff_user.get_full_name() or self.staff_user.username
        )

    def test_reviewer_can_deny_renewal(self):
        consultant = self._create_consultant("Denied Renewal", "approved", timezone.now())
        consultant = self._issue_certificate(consultant, issued_days_ago=360)
        renewal = CertificateRenewal.objects.create(consultant=consultant)

        url = reverse("certificate_renewal_requests")
        self.client.force_login(self.board_user)

        response = self.client.post(
            url,
            {
                "renewal_id": renewal.pk,
                "decision": "deny",
                "notes": "Missing documentation",
            },
            follow=True,
        )

        self.assertRedirects(response, url)
        renewal.refresh_from_db()
        self.assertEqual(renewal.status, CertificateRenewal.Status.DENIED)
        self.assertEqual(renewal.notes, "Missing documentation")

    @patch("apps.decisions.services.transaction.on_commit")
    @patch("apps.decisions.services.generate_rejection_letter_task.delay")
    @patch("apps.decisions.services.generate_approval_certificate_task.delay")
    def test_application_detail_actions(
        self,
        mock_generate_certificate,
        mock_generate_rejection,
        mock_on_commit,
    ):
        self.client.force_login(self.board_user)

        mock_on_commit.side_effect = lambda func, using=None: func()

        scenarios = {
            "vetted": {
                "expected_status": "vetted",
            },
            "approved": {
                "expected_status": "approved",
            },
            "rejected": {
                "expected_status": "rejected",
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

                mock_generate_certificate.reset_mock()
                mock_generate_rejection.reset_mock()
                mock_on_commit.reset_mock()
                mock_on_commit.side_effect = lambda func, using=None: func()

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

                mock_on_commit.assert_called_once()
                generated_by = self.board_user.get_full_name() or self.board_user.username
                if action == "approved":
                    mock_generate_certificate.assert_called_once_with(
                        consultant.pk, generated_by
                    )
                    mock_generate_rejection.assert_not_called()
                elif action == "rejected":
                    mock_generate_rejection.assert_called_once_with(
                        consultant.pk, generated_by
                    )
                    mock_generate_certificate.assert_not_called()
                else:
                    mock_generate_certificate.assert_not_called()
                    mock_generate_rejection.assert_not_called()

                action_record = ApplicationAction.objects.get(consultant=consultant)
                self.assertEqual(action_record.action, action)
