import os
import shutil
import tempfile
from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.consultants.models import Consultant
from .models import ApplicationAction


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

        consultant.refresh_from_db()
        self.assertEqual(consultant.status, "rejected")
        self.assertTrue(consultant.rejection_letter)
        self.assertIsNotNone(consultant.rejection_letter_generated_at)

        response = self.client.get(url)
        self.assertContains(response, "Rejection letter")


class DecisionsDashboardViewTests(TestCase):
    def setUp(self):
        self.UserModel = get_user_model()
        self.reviewer_group, _ = Group.objects.get_or_create(name="BackOffice")

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

        self.consultant_vetted.refresh_from_db()
        self.assertEqual(self.consultant_vetted.status, "rejected")
