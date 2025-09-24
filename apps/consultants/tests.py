import base64
import shutil
import tempfile
from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .forms import ConsultantForm
from .models import Consultant


class ConsultantTestMixin:
    def setUp(self):
        super().setUp()
        self.media_root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media_root, ignore_errors=True)

        override = override_settings(MEDIA_ROOT=self.media_root)
        override.enable()
        self.addCleanup(override.disable)

        self.valid_data = {
            'full_name': 'John Doe',
            'id_number': '123456789',
            'dob': date(1990, 1, 1).isoformat(),
            'gender': 'M',
            'nationality': 'Testland',
            'email': 'john@example.com',
            'phone_number': '1234567890',
            'business_name': 'Doe Consulting',
            'registration_number': 'REG123',
        }

    def _valid_files(self):
        photo_content = base64.b64decode(
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4z8AAAAMBAQDJ/pLvAAAAAElFTkSuQmCC'
        )

        return {
            'photo': SimpleUploadedFile('photo.png', photo_content, content_type='image/png'),
            'id_document': SimpleUploadedFile('id.pdf', b'a' * 1024, content_type='application/pdf'),
            'cv': SimpleUploadedFile('cv.pdf', b'a' * 1024, content_type='application/pdf'),
            'police_clearance': SimpleUploadedFile('police.pdf', b'a' * 1024, content_type='application/pdf'),
            'qualifications': SimpleUploadedFile('qualifications.pdf', b'a' * 1024, content_type='application/pdf'),
            'business_certificate': SimpleUploadedFile('certificate.pdf', b'a' * 1024, content_type='application/pdf'),
        }


class ConsultantFormTests(ConsultantTestMixin, TestCase):

    def test_clean_allows_missing_documents_when_saving_draft(self):
        form = ConsultantForm(data={**self.valid_data, 'action': 'draft'})

        self.assertTrue(form.is_valid())
        for field in ConsultantForm.DOCUMENT_FIELDS:
            self.assertNotIn(field, form.errors)

    def test_clean_requires_documents_on_submit(self):
        form = ConsultantForm(data={**self.valid_data, 'action': 'submit'})

        self.assertFalse(form.is_valid())

        for field in ConsultantForm.DOCUMENT_FIELDS:
            self.assertIn(field, form.errors)
            self.assertIn('This document is required.', form.errors[field])

    def test_clean_rejects_oversize_documents_on_submit(self):
        files = self._valid_files()
        files['cv'] = SimpleUploadedFile(
            'cv.pdf',
            b'a' * (2 * 1024 * 1024 + 1),
            content_type='application/pdf'
        )

        form = ConsultantForm(data={**self.valid_data, 'action': 'submit'}, files=files)

        self.assertFalse(form.is_valid())
        self.assertIn('File size must be under 2MB.', form.errors['cv'])

    def test_clean_rejects_invalid_file_types_on_submit(self):
        files = self._valid_files()
        files['id_document'] = SimpleUploadedFile(
            'id.txt', b'a' * 1024, content_type='text/plain'
        )

        form = ConsultantForm(data={**self.valid_data, 'action': 'submit'}, files=files)

        self.assertFalse(form.is_valid())
        self.assertIn('Only PDF, JPG, or PNG files are allowed.', form.errors['id_document'])

    def test_edit_draft_retains_existing_documents_on_submit(self):
        user_model = get_user_model()
        user = user_model.objects.create_user(username='consultant', password='password')

        stored_files = self._valid_files()

        consultant = Consultant.objects.create(
            user=user,
            full_name='John Doe',
            id_number='123456789',
            dob=date(1990, 1, 1),
            gender='M',
            nationality='Testland',
            email='john@example.com',
            phone_number='1234567890',
            business_name='Doe Consulting',
            registration_number='REG123',
            photo=stored_files['photo'],
            id_document=stored_files['id_document'],
            cv=stored_files['cv'],
            police_clearance=stored_files['police_clearance'],
            qualifications=stored_files['qualifications'],
            business_certificate=stored_files['business_certificate'],
            status='draft',
        )

        form = ConsultantForm(
            data={**self.valid_data, 'action': 'submit'},
            instance=consultant,
        )

        self.assertTrue(form.is_valid(), form.errors)


class ConsultantSubmitApplicationViewTests(ConsultantTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username='consultant', password='password')
        self.client.login(username='consultant', password='password')
        self.url = reverse('submit_application')

    def test_post_draft_saves_application_as_draft(self):
        response = self.client.post(
            self.url,
            {**self.valid_data, 'action': 'draft'},
            follow=True,
        )

        self.assertRedirects(response, reverse('dashboard'))
        consultant = Consultant.objects.get(user=self.user)
        self.assertEqual(consultant.status, 'draft')
        messages = [message.message for message in get_messages(response.wsgi_request)]
        self.assertIn("Draft saved. You can complete it later.", messages)

    def test_post_submit_saves_application_as_submitted(self):
        post_data = {**self.valid_data, 'action': 'submit', **self._valid_files()}
        response = self.client.post(self.url, post_data, follow=True)

        self.assertRedirects(response, reverse('dashboard'))
        consultant = Consultant.objects.get(user=self.user)
        self.assertEqual(consultant.status, 'submitted')
        messages = [message.message for message in get_messages(response.wsgi_request)]
        self.assertIn("Application submitted successfully.", messages)
