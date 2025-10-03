import mimetypes

from django import forms
from django.core.files.uploadedfile import UploadedFile
from django.db.models.fields.files import FieldFile

from .models import Consultant


class ConsultantForm(forms.ModelForm):
    DOCUMENT_FIELDS = [
        'photo',
        'id_document',
        'cv',
        'police_clearance',
        'qualifications',
        'business_certificate',
    ]
    MAX_FILE_SIZE = 2 * 1024 * 1024  # 2MB
    ALLOWED_CONTENT_TYPES = ['application/pdf', 'image/jpeg', 'image/png']

    def clean(self):
        cleaned_data = super().clean()
        action = self.data.get('action', 'draft')

        if action == 'submit':
            for field in self.DOCUMENT_FIELDS:
                file = cleaned_data.get(field)

                if file is False:
                    cleaned_data[field] = None
                    self.add_error(field, "This document is required.")
                    continue

                if isinstance(file, (UploadedFile, FieldFile)):
                    self._validate_file(field, file)
                else:
                    existing_file = getattr(self.instance, field, None)
                    if existing_file:
                        self._validate_file(field, existing_file)
                    else:
                        self.add_error(field, "This document is required.")

        return cleaned_data

    def _validate_file(self, field, file_obj):
        try:
            size = file_obj.size
        except Exception:  # pragma: no cover - defensive, should not occur in tests
            size = None

        if size and size > self.MAX_FILE_SIZE:
            self.add_error(field, "File size must be under 2MB.")

        content_type = getattr(file_obj, 'content_type', None)
        if not content_type and hasattr(file_obj, 'file'):
            content_type = getattr(file_obj.file, 'content_type', None)
        if not content_type and hasattr(file_obj, 'name'):
            guessed_type, _ = mimetypes.guess_type(file_obj.name)
            content_type = guessed_type

        if content_type and content_type not in self.ALLOWED_CONTENT_TYPES:
            self.add_error(field, "Only PDF, JPG, or PNG files are allowed.")

    class Meta:
        model = Consultant
        exclude = ['user', 'submitted_at', 'status']
        widgets = {
            'dob': forms.DateInput(attrs={'type': 'date'}),
        }
