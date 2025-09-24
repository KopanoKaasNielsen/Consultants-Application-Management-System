from datetime import date

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from .forms import ConsultantForm


class ConsultantFormTests(TestCase):
    def setUp(self):
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
        return {
            'photo': SimpleUploadedFile('photo.jpg', b'a' * 1024, content_type='image/jpeg'),
            'id_document': SimpleUploadedFile('id.pdf', b'a' * 1024, content_type='application/pdf'),
            'cv': SimpleUploadedFile('cv.pdf', b'a' * 1024, content_type='application/pdf'),
            'police_clearance': SimpleUploadedFile('police.pdf', b'a' * 1024, content_type='application/pdf'),
            'qualifications': SimpleUploadedFile('qualifications.pdf', b'a' * 1024, content_type='application/pdf'),
            'business_certificate': SimpleUploadedFile('certificate.pdf', b'a' * 1024, content_type='application/pdf'),
        }

    def test_clean_requires_documents(self):
        form = ConsultantForm(data=self.valid_data)

        self.assertFalse(form.is_valid())

        required_docs = [
            'photo', 'id_document', 'cv', 'police_clearance',
            'qualifications', 'business_certificate'
        ]

        for field in required_docs:
            self.assertIn(field, form.errors)
            self.assertIn('This document is required.', form.errors[field])

    def test_clean_rejects_oversize_documents(self):
        files = self._valid_files()
        files['cv'] = SimpleUploadedFile(
            'cv.pdf',
            b'a' * (2 * 1024 * 1024 + 1),
            content_type='application/pdf'
        )

        form = ConsultantForm(data=self.valid_data, files=files)

        self.assertFalse(form.is_valid())
        self.assertIn('File size must be under 2MB.', form.errors['cv'])

    def test_clean_rejects_invalid_file_types(self):
        files = self._valid_files()
        files['id_document'] = SimpleUploadedFile(
            'id.txt', b'a' * 1024, content_type='text/plain'
        )

        form = ConsultantForm(data=self.valid_data, files=files)

        self.assertFalse(form.is_valid())
        self.assertIn('Only PDF, JPG, or PNG files are allowed.', form.errors['id_document'])
