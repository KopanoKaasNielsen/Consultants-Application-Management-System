from django import forms
from django.core.files.uploadedfile import UploadedFile

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
        action = self.data.get('action')

        if action == 'submit':
            for field in self.DOCUMENT_FIELDS:
                file = cleaned_data.get(field)

                if isinstance(file, UploadedFile):
                    if file.size > self.MAX_FILE_SIZE:
                        self.add_error(field, "File size must be under 2MB.")
                    if file.content_type not in self.ALLOWED_CONTENT_TYPES:
                        self.add_error(field, "Only PDF, JPG, or PNG files are allowed.")
                elif file:
                    # Existing file retained, nothing to validate.
                    continue
                else:
                    existing_file = getattr(self.instance, field, None)
                    if not existing_file:
                        self.add_error(field, "This document is required.")

        return cleaned_data

    class Meta:
        model = Consultant
        exclude = ['user', 'submitted_at', 'status']
        widgets = {
            'dob': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.DOCUMENT_FIELDS:
            if field in self.fields:
                self.fields[field].required = False
