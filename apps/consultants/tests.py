import io
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from .forms import ConsultantForm
from .models import Consultant


def create_image_file(name='photo.png'):
    buffer = io.BytesIO()
    image = Image.new('RGB', (1, 1), color='white')
    image.save(buffer, format='PNG')
    return SimpleUploadedFile(name, buffer.getvalue(), content_type='image/png')


def create_pdf_file(name='document.pdf', size=1024, content_type='application/pdf'):
    return SimpleUploadedFile(name, b'a' * size, content_type=content_type)


class ConsultantFormTests(TestCase):
    def setUp(self):
        self.base_data = {
            'full_name': 'Test User',
            'id_number': 'ID123456',
            'dob': '1990-01-01',
            'gender': 'M',
            'nationality': 'Testland',
            'email': 'test@example.com',
            'phone_number': '1234567890',
            'business_name': 'Test Business',
            'registration_number': 'REG123',
        }

    def _get_form(self, action, files=None):
        data = {**self.base_data, 'action': action}
        return ConsultantForm(data=data, files=files)

    def test_draft_allows_missing_documents(self):
        form = self._get_form('draft')
        self.assertTrue(form.is_valid(), form.errors)

    def test_submit_requires_documents(self):
        form = self._get_form('submit')
        self.assertFalse(form.is_valid())
        for field in ConsultantForm.DOCUMENT_FIELDS:
            self.assertIn(field, form.errors)
            self.assertIn('This document is required.', form.errors[field])

    def test_submit_rejects_large_files(self):
        oversized_cv = create_pdf_file(
            size=ConsultantForm.MAX_FILE_SIZE + 1,
            name='cv.pdf',
        )
        files = {
            'photo': create_image_file(),
            'id_document': create_pdf_file(name='id.pdf'),
            'cv': oversized_cv,
            'police_clearance': create_pdf_file(name='police.pdf'),
            'qualifications': create_pdf_file(name='qualifications.pdf'),
            'business_certificate': create_pdf_file(name='certificate.pdf'),
        }
        form = self._get_form('submit', files=files)
        self.assertFalse(form.is_valid())
        self.assertIn('File size must be under 2MB.', form.errors['cv'])

    def test_submit_rejects_invalid_file_type(self):
        invalid_cv = create_pdf_file(
            name='cv.exe',
            content_type='application/x-msdownload',
        )
        files = {
            'photo': create_image_file(),
            'id_document': create_pdf_file(name='id.pdf'),
            'cv': invalid_cv,
            'police_clearance': create_pdf_file(name='police.pdf'),
            'qualifications': create_pdf_file(name='qualifications.pdf'),
            'business_certificate': create_pdf_file(name='certificate.pdf'),
        }
        form = self._get_form('submit', files=files)
        self.assertFalse(form.is_valid())
        self.assertIn('Only PDF, JPG, or PNG files are allowed.', form.errors['cv'])

    def test_submit_accepts_valid_documents(self):
        files = {
            'photo': create_image_file(),
            'id_document': create_pdf_file(name='id.pdf'),
            'cv': create_pdf_file(name='cv.pdf'),
            'police_clearance': create_pdf_file(name='police.pdf'),
            'qualifications': create_pdf_file(name='qualifications.pdf'),
            'business_certificate': create_pdf_file(name='certificate.pdf'),
        }
        form = self._get_form('submit', files=files)
        self.assertTrue(form.is_valid(), form.errors)


class SubmitApplicationViewTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user('applicant', password='password123')
        self.client.force_login(self.user)
        self.base_payload = {
            'full_name': 'Applicant User',
            'id_number': 'ID999999',
            'dob': '1995-05-05',
            'gender': 'F',
            'nationality': 'Examplestan',
            'email': 'applicant@example.com',
            'phone_number': '5551234',
            'business_name': 'Applicant Biz',
            'registration_number': 'REG999',
        }

    def _submit(self, action, extra_files=None):
        payload = {**self.base_payload, 'action': action}
        if extra_files:
            payload.update(extra_files)
        return self.client.post(reverse('submit_application'), payload, follow=True)

    def test_draft_submission_leaves_timestamp_empty(self):
        response = self._submit('draft')
        self.assertEqual(response.status_code, 200)

        application = Consultant.objects.get(user=self.user)
        self.assertEqual(application.status, 'draft')
        self.assertIsNone(application.submitted_at)

    def test_submit_sets_submitted_timestamp(self):
        # Start with a draft so we can follow the normal flow
        self._submit('draft')

        files = {
            'photo': create_image_file(),
            'id_document': create_pdf_file(name='id.pdf'),
            'cv': create_pdf_file(name='cv.pdf'),
            'police_clearance': create_pdf_file(name='police.pdf'),
            'qualifications': create_pdf_file(name='qualifications.pdf'),
            'business_certificate': create_pdf_file(name='certificate.pdf'),
        }

        response = self._submit('submit', extra_files=files)
        self.assertEqual(response.status_code, 200)

        application = Consultant.objects.get(user=self.user)
        self.assertEqual(application.status, 'submitted')
        self.assertIsNotNone(application.submitted_at)
        self.assertLess(timezone.now() - application.submitted_at, timedelta(seconds=5))
