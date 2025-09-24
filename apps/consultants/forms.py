from django import forms
from .models import Consultant

class ConsultantForm(forms.ModelForm):
    class Meta:
        model = Consultant
        exclude = ['user', 'submitted_at', 'status']
        widgets = {
            'dob': forms.DateInput(attrs={'type': 'date'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        required_docs = [
            'photo',
            'id_document',
            'cv',
            'police_clearance',
            'qualifications',
            'business_certificate',
        ]

        for field in required_docs:
            file = cleaned_data.get(field)
            if file:
                if file.size > 2 * 1024 * 1024:  # 2MB
                    self.add_error(field, "File size must be under 2MB.")
                if file.content_type not in ['application/pdf', 'image/jpeg', 'image/png']:
                    self.add_error(field, "Only PDF, JPG, or PNG files are allowed.")
            else:
                self.add_error(field, "This document is required.")

        return cleaned_data
