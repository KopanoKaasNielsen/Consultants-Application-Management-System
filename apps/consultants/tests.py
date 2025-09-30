import io

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image

from .forms import ConsultantForm


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

    def _create_image_file(self, name='photo.png'):
        buffer = io.BytesIO()
        image = Image.new('RGB', (1, 1), color='white')
        image.save(buffer, format='PNG')
        return SimpleUploadedFile(name, buffer.getvalue(), content_type='image/png')

    def _create_pdf_file(self, name='document.pdf', size=1024, content_type='application/pdf'):
        return SimpleUploadedFile(name, b'a' * size, content_type=content_type)

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
        oversized_cv = self._create_pdf_file(
            size=ConsultantForm.MAX_FILE_SIZE + 1,
            name='cv.pdf',
        )
        files = {
            'photo': self._create_image_file(),
            'id_document': self._create_pdf_file(name='id.pdf'),
            'cv': oversized_cv,
            'police_clearance': self._create_pdf_file(name='police.pdf'),
            'qualifications': self._create_pdf_file(name='qualifications.pdf'),
            'business_certificate': self._create_pdf_file(name='certificate.pdf'),
        }
        form = self._get_form('submit', files=files)
        self.assertFalse(form.is_valid())
        self.assertIn('File size must be under 2MB.', form.errors['cv'])

    def test_submit_rejects_invalid_file_type(self):
        invalid_cv = self._create_pdf_file(
            name='cv.exe',
            content_type='application/x-msdownload',
        )
        files = {
            'photo': self._create_image_file(),
            'id_document': self._create_pdf_file(name='id.pdf'),
            'cv': invalid_cv,
            'police_clearance': self._create_pdf_file(name='police.pdf'),
            'qualifications': self._create_pdf_file(name='qualifications.pdf'),
            'business_certificate': self._create_pdf_file(name='certificate.pdf'),
        }
        form = self._get_form('submit', files=files)
        self.assertFalse(form.is_valid())
        self.assertIn('Only PDF, JPG, or PNG files are allowed.', form.errors['cv'])

    def test_submit_accepts_valid_documents(self):
        files = {
            'photo': self._create_image_file(),
            'id_document': self._create_pdf_file(name='id.pdf'),
            'cv': self._create_pdf_file(name='cv.pdf'),
            'police_clearance': self._create_pdf_file(name='police.pdf'),
            'qualifications': self._create_pdf_file(name='qualifications.pdf'),
            'business_certificate': self._create_pdf_file(name='certificate.pdf'),
        }
        form = self._get_form('submit', files=files)
        self.assertTrue(form.is_valid(), form.errors)
