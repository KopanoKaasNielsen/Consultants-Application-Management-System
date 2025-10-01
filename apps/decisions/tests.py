import os
import shutil
import tempfile
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.consultants.models import Consultant


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

        consultant.refresh_from_db()
        self.assertEqual(consultant.status, "rejected")
        self.assertTrue(consultant.rejection_letter)
        self.assertIsNotNone(consultant.rejection_letter_generated_at)

        response = self.client.get(url)
        self.assertContains(response, "Rejection letter")
