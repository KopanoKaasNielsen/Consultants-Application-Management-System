from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.consultants.models import Consultant
from apps.users.constants import (
    BACKOFFICE_GROUP_NAME,
    CONSULTANTS_GROUP_NAME,
)


class CertificatesDashboardViewTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.user = self.user_model.objects.create_user(
            "consultant_user", password="strong-password"
        )
        consultant_group, _ = Group.objects.get_or_create(name=CONSULTANTS_GROUP_NAME)
        self.user.groups.add(consultant_group)
        self.dashboard_url = reverse("certificates:certificates_dashboard")

    def _create_consultant(self, user, **overrides):
        defaults = {
            "full_name": "Sample Consultant",
            "id_number": "ID123456",
            "dob": date(1990, 1, 1),
            "gender": "M",
            "nationality": "Testland",
            "email": "consultant@example.com",
            "phone_number": "1234567890",
            "business_name": "Consulting LLC",
            "registration_number": "REG123",
            "status": "approved",
        }
        defaults.update(overrides)
        return Consultant.objects.create(user=user, **defaults)

    def test_dashboard_requires_authentication(self):
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response["Location"])

    def test_dashboard_handles_users_without_consultant_profile(self):
        self.client.force_login(self.user)

        response = self.client.get(self.dashboard_url)

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["consultant"])
        self.assertContains(response, "could not find an application", status_code=200)

    def test_dashboard_displays_documents_for_logged_in_consultant(self):
        certificate_file = SimpleUploadedFile(
            "approval.pdf", b"certificate", content_type="application/pdf"
        )
        rejection_file = SimpleUploadedFile(
            "rejection.pdf", b"rejection", content_type="application/pdf"
        )

        consultant = self._create_consultant(
            self.user,
            full_name="Primary Consultant",
            certificate_pdf=certificate_file,
            rejection_letter=rejection_file,
        )

        certificate_filename = consultant.certificate_pdf.name.split("/")[-1]
        rejection_filename = consultant.rejection_letter.name.split("/")[-1]

        other_user = self.user_model.objects.create_user(
            "other_user", password="strong-password"
        )
        self._create_consultant(
            other_user,
            full_name="Other Consultant",
            certificate_pdf=SimpleUploadedFile(
                "other.pdf", b"other", content_type="application/pdf"
            ),
        )

        self.client.force_login(self.user)
        response = self.client.get(self.dashboard_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["consultant"], consultant)
        self.assertContains(response, "Approval certificate")
        self.assertContains(response, "Rejection letter")
        self.assertContains(response, certificate_filename)
        self.assertContains(response, rejection_filename)
        self.assertNotContains(response, "Other Consultant")

    def test_dashboard_displays_success_message_when_certificate_available(self):
        certificate_file = SimpleUploadedFile(
            "approval.pdf", b"certificate", content_type="application/pdf"
        )

        consultant = self._create_consultant(
            self.user,
            status="approved",
            certificate_pdf=certificate_file,
        )

        self.client.force_login(self.user)
        response = self.client.get(self.dashboard_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["consultant"], consultant)

        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(messages)
        self.assertIn("Application approved!", str(messages[0]))

    def test_non_consultant_user_receives_403(self):
        staff_user = self.user_model.objects.create_user(
            "staff_only", password="strong-password"
        )
        staff_group, _ = Group.objects.get_or_create(name=BACKOFFICE_GROUP_NAME)
        staff_user.groups.add(staff_group)

        self.client.force_login(staff_user)

        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 403)
