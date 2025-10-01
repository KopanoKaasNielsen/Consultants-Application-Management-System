import os
import shutil
import tempfile
from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.consultants.models import Consultant
from .models import ApplicationAction
from apps.users.constants import (
    BACKOFFICE_GROUP_NAME,
    BOARD_COMMITTEE_GROUP_NAME,
    CONSULTANTS_GROUP_NAME,
)


class ApplicationDecisionDocumentTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._temp_media = tempfile.mkdtemp()
        cls._override = override_settings(MEDIA_ROOT=cls._temp_media)
        cls._override.enable()

    @classmethod
    def tearDownClass(cls):
        cls._override.disable()
        shutil.rmtree(cls._temp_media, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.UserModel = get_user_model()
        self.reviewer = self.UserModel.objects.create_superuser(
            username="reviewer", email="reviewer@example.com", password="pass1234"
        )
        self.client.login(username="reviewer", password="pass1234")

    def create_application(self):
        applicant = self.UserModel.objects.create_user(
            username="applicant" + os.urandom(2).hex(),
            email="applicant@example.com",
            password="pass1234",
        )
        return Consultant.objects.create(
            user=applicant,
            full_name="Test Applicant",
            id_number="ID123456",
            dob=date(1990, 1, 1),
            gender="M",
            nationality="Testland",
            email="applicant@example.com",
            phone_number="123456789",
            business_name="Test Business",
            registration_number="REG-001",
        )

    def test_approval_generates_certificate(self):
        consultant = self.create_application()
        url = reverse("officer_application_detail", args=[consultant.pk])

        response = self.client.post(url, {"action": "approved", "notes": "Looks good"}, follow=True)
        self.assertEqual(response.status_code, 200)

        messages = list(response.context["messages"])
        self.assertIn("Application approved.", [message.message for message in messages])

        self.assertEqual(len(mail.outbox), 1)
        approval_email = mail.outbox[0]
        self.assertEqual(
            approval_email.subject,
            "Your consultant application has been approved",
        )
        self.assertEqual(approval_email.to, [consultant.email])

        consultant.refresh_from_db()
        self.assertEqual(consultant.status, "approved")
        self.assertTrue(consultant.certificate_pdf)
        self.assertIsNotNone(consultant.certificate_generated_at)

        response = self.client.get(url)
        self.assertContains(response, "Approval certificate")

    def test_rejection_generates_letter(self):
        consultant = self.create_application()
        url = reverse("officer_application_detail", args=[consultant.pk])

        response = self.client.post(url, {"action": "rejected", "notes": "Incomplete"}, follow=True)
        self.assertEqual(response.status_code, 200)

        messages = list(response.context["messages"])
        self.assertIn(
            "Application has been rejected.",
            [message.message for message in messages],
        )

        self.assertEqual(len(mail.outbox), 1)
        rejection_email = mail.outbox[0]
        self.assertEqual(
            rejection_email.subject,
            "Update on your consultant application",
        )
        self.assertEqual(rejection_email.to, [consultant.email])

        consultant.refresh_from_db()
        self.assertEqual(consultant.status, "rejected")
        self.assertTrue(consultant.rejection_letter)
        self.assertIsNotNone(consultant.rejection_letter_generated_at)

        response = self.client.get(url)
        self.assertContains(response, "Rejection letter")


class DecisionsDashboardViewTests(TestCase):
    def setUp(self):
        self.UserModel = get_user_model()
        self.reviewer_group, _ = Group.objects.get_or_create(name=BACKOFFICE_GROUP_NAME)

        self.reviewer = self.UserModel.objects.create_user(
            username="reviewer",
            email="reviewer@example.com",
            password="pass1234",
        )
        self.reviewer.groups.add(self.reviewer_group)

        self.client.login(username="reviewer", password="pass1234")

        self.consultant_user = self.UserModel.objects.create_user(
            username="consultant",
            email="consultant@example.com",
            password="pass1234",
        )
        self.consultant_vetted = Consultant.objects.create(
            user=self.consultant_user,
            full_name="Vetted Applicant",
            id_number="ID0001",
            dob=date(1990, 1, 1),
            gender="F",
            nationality="Exampleland",
            email="consultant@example.com",
            phone_number="123456789",
            business_name="Vet Consulting",
            registration_number="REG-123",
            status="vetted",
        )
        self.consultant_submitted = Consultant.objects.create(
            user=self.UserModel.objects.create_user(
                username="submitted", email="submitted@example.com", password="pass1234"
            ),
            full_name="Submitted Applicant",
            id_number="ID0002",
            dob=date(1992, 5, 5),
            gender="M",
            nationality="Exampleland",
            email="submitted@example.com",
            phone_number="987654321",
            business_name="Sub Consulting",
            registration_number="REG-456",
            status="submitted",
        )

    def test_reviewer_can_access_dashboard(self):
        response = self.client.get(reverse("decisions_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Vetted Applicant")
        self.assertNotContains(response, "Submitted Applicant")

    def test_non_reviewer_gets_403(self):
        other_user = self.UserModel.objects.create_user(
            username="nonreviewer", email="non@example.com", password="pass1234"
        )
        self.client.logout()
        self.client.login(username="nonreviewer", password="pass1234")

        response = self.client.get(reverse("decisions_dashboard"))
        self.assertEqual(response.status_code, 403)

    def test_board_member_can_access_dashboard(self):
        board_user = self.UserModel.objects.create_user(
            username="boardmember", email="board@example.com", password="pass1234"
        )
        board_group, _ = Group.objects.get_or_create(name=BOARD_COMMITTEE_GROUP_NAME)
        board_user.groups.add(board_group)

        self.client.logout()
        self.client.login(username="boardmember", password="pass1234")

        response = self.client.get(reverse("decisions_dashboard"))
        self.assertEqual(response.status_code, 200)

    def test_reviewer_can_record_action(self):
        response = self.client.post(
            reverse("decisions_dashboard"),
            data={
                "consultant_id": self.consultant_vetted.pk,
                "action": "vetted",
                "notes": "Checked and ready.",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)

        messages = list(response.context["messages"])
        self.assertIn(
            "Application has been vetted.",
            [message.message for message in messages],
        )

        self.consultant_vetted.refresh_from_db()
        self.assertEqual(self.consultant_vetted.status, "vetted")
        self.assertTrue(
            ApplicationAction.objects.filter(
                consultant=self.consultant_vetted,
                actor=self.reviewer,
                action="vetted",
            ).exists()
        )

    def test_approved_application_removed_from_dashboard(self):
        """Approving a vetted application removes it from the decision queue."""

        # Ensure the vetted application is initially visible on the dashboard
        initial_response = self.client.get(reverse("decisions_dashboard"))
        self.assertContains(initial_response, "Vetted Applicant")

        # Approve the application via the dashboard action form
        post_response = self.client.post(
            reverse("decisions_dashboard"),
            data={
                "consultant_id": self.consultant_vetted.pk,
                "action": "approved",
                "notes": "Ready for approval.",
            },
            follow=True,
        )
        self.assertEqual(post_response.status_code, 200)

        messages = list(post_response.context["messages"])
        self.assertIn(
            "Application approved.",
            [message.message for message in messages],
        )

        self.assertEqual(len(mail.outbox), 1)
        approval_email = mail.outbox[0]
        self.assertEqual(
            approval_email.subject,
            "Your consultant application has been approved",
        )
        self.assertEqual(approval_email.to, [self.consultant_vetted.email])

        # The application should now be approved and no longer listed
        self.consultant_vetted.refresh_from_db()
        self.assertEqual(self.consultant_vetted.status, "approved")

        dashboard_response = self.client.get(reverse("decisions_dashboard"))
        self.assertNotContains(dashboard_response, "Vetted Applicant")

    def test_dashboard_rejection_message(self):
        response = self.client.post(
            reverse("decisions_dashboard"),
            data={
                "consultant_id": self.consultant_vetted.pk,
                "action": "rejected",
                "notes": "Missing documents.",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)

        messages = list(response.context["messages"])
        self.assertIn(
            "Application has been rejected.",
            [message.message for message in messages],
        )

        self.assertEqual(len(mail.outbox), 1)
        rejection_email = mail.outbox[0]
        self.assertEqual(
            rejection_email.subject,
            "Update on your consultant application",
        )
        self.assertEqual(rejection_email.to, [self.consultant_vetted.email])

        self.consultant_vetted.refresh_from_db()
        self.assertEqual(self.consultant_vetted.status, "rejected")


class OfficerApplicationsListViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.UserModel = get_user_model()
        cls.reviewer_group, _ = Group.objects.get_or_create(name=BACKOFFICE_GROUP_NAME)
        cls.consultant_group, _ = Group.objects.get_or_create(name=CONSULTANTS_GROUP_NAME)

        cls.consultants_by_status = {}
        for index, status in enumerate(["draft", "submitted", "vetted", "approved", "rejected"], start=1):
            user = cls.UserModel.objects.create_user(
                username=f"consultant_{status}",
                email=f"{status}@example.com",
                password="pass1234",
            )
            cls.consultants_by_status[status] = Consultant.objects.create(
                user=user,
                full_name=f"Consultant {status.title()}",
                id_number=f"ID{index:04d}",
                dob=date(1990, 1, index if index <= 28 else 28),
                gender="M" if index % 2 else "F",
                nationality="Testland",
                email=f"{status}@example.com",
                phone_number=f"1234567{index:02d}",
                business_name=f"Business {status.title()}",
                registration_number=f"REG-{index:03d}",
                status=status,
                submitted_at=timezone.now(),
            )

    def setUp(self):
        self.reviewer = self.UserModel.objects.create_user(
            username="staff_reviewer",
            email="staff@example.com",
            password="pass1234",
        )
        self.reviewer.groups.add(self.reviewer_group)

    def test_reviewer_sees_default_filtered_statuses(self):
        self.client.login(username="staff_reviewer", password="pass1234")

        response = self.client.get(reverse("officer_applications_list"))

        self.assertEqual(response.status_code, 200)

        applications = list(response.context["applications"])
        returned_statuses = {application.status for application in applications}
        self.assertEqual(returned_statuses, {"submitted", "vetted"})
        self.assertEqual(response.context["active_status"], "submitted,vetted")

        disallowed_statuses = {"draft", "approved", "rejected"}
        for status in disallowed_statuses:
            self.assertNotIn(self.consultants_by_status[status], applications)

    def test_non_reviewer_gets_403(self):
        consultant_user = self.UserModel.objects.create_user(
            username="non_reviewer",
            email="nonreviewer@example.com",
            password="pass1234",
        )
        consultant_user.groups.add(self.consultant_group)

        self.client.login(username="non_reviewer", password="pass1234")

        response = self.client.get(reverse("officer_applications_list"))
        self.assertEqual(response.status_code, 403)
