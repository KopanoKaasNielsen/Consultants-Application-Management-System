import io
import json
import shutil
import tempfile
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from .forms import ConsultantForm
from .models import Consultant, Notification
from apps.users.constants import (
    BACKOFFICE_GROUP_NAME,
    CONSULTANTS_GROUP_NAME,
)


def create_image_file(name='photo.png'):
    buffer = io.BytesIO()
    image = Image.new('RGB', (1, 1), color='white')
    image.save(buffer, format='PNG')
    return SimpleUploadedFile(name, buffer.getvalue(), content_type='image/png')


def create_pdf_file(name='document.pdf', size=1024, content_type='application/pdf'):
    return SimpleUploadedFile(name, b'a' * size, content_type=content_type)


class ConsultantFormTests(TestCase):
    def setUp(self):
        self.temp_media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.temp_media)
        override = override_settings(MEDIA_ROOT=self.temp_media)
        override.enable()
        self.addCleanup(override.disable)

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
        self.model_defaults = {
            'full_name': 'Test User',
            'id_number': 'ID123456',
            'dob': date(1990, 1, 1),
            'gender': 'M',
            'nationality': 'Testland',
            'email': 'test@example.com',
            'phone_number': '1234567890',
            'business_name': 'Test Business',
            'registration_number': 'REG123',
        }
        self.user_index = 0

    def _get_form(self, action, files=None):
        data = {**self.base_data, 'action': action}
        return ConsultantForm(data=data, files=files)

    def _create_consultant_with_documents(self, **document_overrides):
        user_model = get_user_model()
        self.user_index += 1
        user = user_model.objects.create_user(
            username=f'consultant{self.user_index}',
            email=f'consultant{self.user_index}@example.com',
            password='password123',
        )

        document_defaults = {
            'photo': create_image_file(name=f'photo_{self.user_index}.png'),
            'id_document': create_pdf_file(name=f'id_{self.user_index}.pdf'),
            'cv': create_pdf_file(name=f'cv_{self.user_index}.pdf'),
            'police_clearance': create_pdf_file(name=f'police_{self.user_index}.pdf'),
            'qualifications': create_pdf_file(name=f'qualifications_{self.user_index}.pdf'),
            'business_certificate': create_pdf_file(name=f'certificate_{self.user_index}.pdf'),
        }
        document_defaults.update(document_overrides)

        consultant = Consultant.objects.create(
            user=user,
            **self.model_defaults,
            **document_defaults,
        )
        return consultant

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

    def test_submit_rejects_retained_large_existing_file(self):
        consultant = self._create_consultant_with_documents(
            cv=create_pdf_file(
                name='existing_cv.pdf',
                size=ConsultantForm.MAX_FILE_SIZE + 1,
            )
        )

        form = ConsultantForm(
            data={**self.base_data, 'action': 'submit'},
            instance=consultant,
        )

        self.assertFalse(form.is_valid())
        self.assertIn('File size must be under 2MB.', form.errors['cv'])

    def test_submit_rejects_retained_invalid_mime_type(self):
        consultant = self._create_consultant_with_documents(
            cv=create_pdf_file(
                name='existing_cv.exe',
                content_type='application/x-msdownload',
            )
        )

        form = ConsultantForm(
            data={**self.base_data, 'action': 'submit'},
            instance=consultant,
        )

        self.assertFalse(form.is_valid())
        self.assertIn('Only PDF, JPG, or PNG files are allowed.', form.errors['cv'])

    def test_submit_rejects_cleared_document_without_replacement(self):
        consultant = self._create_consultant_with_documents()

        data = {**self.base_data, 'action': 'submit', 'cv-clear': 'on'}
        form = ConsultantForm(data=data, instance=consultant)

        self.assertFalse(form.is_valid())
        self.assertIn('This document is required.', form.errors['cv'])


class SubmitApplicationViewTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user('applicant', password='password123')
        consultant_group, _ = Group.objects.get_or_create(name=CONSULTANTS_GROUP_NAME)
        self.user.groups.add(consultant_group)
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
        self.assertEqual(len(mail.outbox), 0)

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
        self.assertEqual(len(mail.outbox), 1)
        confirmation_email = mail.outbox[0]
        self.assertEqual(confirmation_email.to, ['applicant@example.com'])
        self.assertIn('Applicant User', confirmation_email.body)

    def test_draft_does_not_send_email(self):
        response = self._submit('draft')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

    def test_submission_sends_confirmation_email(self):
        # Create a draft first to follow the expected flow
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
        self.assertEqual(len(mail.outbox), 1)

        confirmation_email = mail.outbox[0]
        self.assertEqual(confirmation_email.subject, 'Consultant Application Submitted')
        self.assertEqual(confirmation_email.to, ['applicant@example.com'])
        self.assertIn('Applicant User', confirmation_email.body)
        self.assertIn('Applicant Biz', confirmation_email.body)

    def test_non_consultant_user_receives_403(self):
        staff_user = get_user_model().objects.create_user(
            'staffer', password='password123'
        )
        staff_group, _ = Group.objects.get_or_create(name=BACKOFFICE_GROUP_NAME)
        staff_user.groups.add(staff_group)

        self.client.force_login(staff_user)

        response = self.client.get(reverse('submit_application'))
        self.assertEqual(response.status_code, 403)


class AutoSaveDraftViewTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user('autosaver', password='password123')
        consultant_group, _ = Group.objects.get_or_create(name=CONSULTANTS_GROUP_NAME)
        self.user.groups.add(consultant_group)
        self.client.force_login(self.user)

        self.consultant = Consultant.objects.create(
            user=self.user,
            full_name='Initial User',
            id_number='ID123456',
            dob=date(1985, 7, 1),
            gender='M',
            nationality='Originland',
            email='initial@example.com',
            phone_number='0700000000',
            business_name='Initial Biz',
            registration_number='REG-001',
        )

    def test_autosave_updates_only_changed_fields(self):
        url = reverse('autosave_consultant_draft')
        payload = {
            'phone_number': '0712345678',
            'business_name': 'Initial Biz',
        }

        response = self.client.post(
            url,
            data=json.dumps(payload),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['status'], 'saved')
        self.assertIn('timestamp', body)

        self.consultant.refresh_from_db()
        self.assertEqual(self.consultant.phone_number, '0712345678')
        self.assertEqual(self.consultant.full_name, 'Initial User')
        self.assertEqual(self.consultant.id_number, 'ID123456')
        self.assertEqual(self.consultant.business_name, 'Initial Biz')
        self.assertEqual(self.consultant.registration_number, 'REG-001')
        self.assertEqual(self.consultant.status, 'draft')


class NotificationViewsTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.user = self.user_model.objects.create_user('notify-user', password='pass123456')
        consultant_group, _ = Group.objects.get_or_create(name=CONSULTANTS_GROUP_NAME)
        self.user.groups.add(consultant_group)
        self.client.force_login(self.user)

        self.notification = Notification.objects.create(
            recipient=self.user,
            message='Test notification',
            notification_type=Notification.NotificationType.APPROVED,
        )

    def test_mark_notification_read_marks_as_read(self):
        response = self.client.post(
            reverse('consultant_notification_mark_read', args=[self.notification.pk]),
            {'next': reverse('dashboard')},
        )

        self.assertRedirects(response, reverse('dashboard'))
        self.notification.refresh_from_db()
        self.assertTrue(self.notification.is_read)

    def test_mark_notification_read_is_scoped_to_owner(self):
        other_user = self.user_model.objects.create_user('other', password='pass123456')
        other_group, _ = Group.objects.get_or_create(name=CONSULTANTS_GROUP_NAME)
        other_user.groups.add(other_group)

        self.client.force_login(other_user)
        response = self.client.post(
            reverse('consultant_notification_mark_read', args=[self.notification.pk]),
            {'next': reverse('dashboard')},
        )

        self.assertEqual(response.status_code, 404)
        self.notification.refresh_from_db()
        self.assertFalse(self.notification.is_read)
