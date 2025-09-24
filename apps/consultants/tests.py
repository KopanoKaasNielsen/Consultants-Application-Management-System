import io

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from .forms import ConsultantForm
from .models import Consultant


def _create_test_image(filename='photo.png'):
    image = Image.new('RGB', (1, 1), 'white')
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    return SimpleUploadedFile(filename, buffer.getvalue(), content_type='image/png')


def _create_pdf(name):
    return SimpleUploadedFile(name, b'%PDF-1.4 test pdf', content_type='application/pdf')


def _valid_form_data():
    return {
        'full_name': 'Jane Doe',
        'id_number': '1234567890',
        'dob': '1990-01-01',
        'gender': 'F',
        'nationality': 'Country',
        'email': 'jane@example.com',
        'phone_number': '+123456789',
        'business_name': 'Jane Consulting',
        'registration_number': 'REG123',
    }


def _valid_form_files():
    return {
        'photo': _create_test_image(),
        'id_document': _create_pdf('id.pdf'),
        'cv': _create_pdf('cv.pdf'),
        'police_clearance': _create_pdf('police.pdf'),
        'qualifications': _create_pdf('qualifications.pdf'),
        'business_certificate': _create_pdf('certificate.pdf'),
    }


class ConsultantFormTests(TestCase):

    def test_rejects_invalid_document_types(self):
        files = _valid_form_files()
        files['id_document'] = SimpleUploadedFile('id.txt', b'invalid', content_type='text/plain')

        form = ConsultantForm(data=_valid_form_data(), files=files)

        self.assertFalse(form.is_valid())
        self.assertIn('Only PDF, JPG, or PNG files are allowed.', form.errors['id_document'])


class SubmitApplicationViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='applicant',
            password='strong-password',
            email='applicant@example.com',
        )
        self.client.force_login(self.user)
        self.url = reverse('submit_application')

    def _post_payload(self, **overrides):
        data = {
            **_valid_form_data(),
            **_valid_form_files(),
            'action': 'draft',
        }
        data.update(overrides)
        return data

    def test_can_save_application_as_draft(self):
        response = self.client.post(self.url, self._post_payload(), follow=True)

        self.assertRedirects(response, reverse('dashboard'))
        consultant = Consultant.objects.get(user=self.user)
        self.assertEqual(consultant.status, 'draft')

    def test_submit_action_marks_application_as_submitted(self):
        response = self.client.post(
            self.url,
            self._post_payload(action='submit'),
            follow=True,
        )

        self.assertRedirects(response, reverse('dashboard'))
        consultant = Consultant.objects.get(user=self.user)
        self.assertEqual(consultant.status, 'submitted')
