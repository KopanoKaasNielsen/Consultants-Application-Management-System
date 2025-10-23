from django import forms
from .models import Certificate
from django.utils import timezone
from datetime import timedelta

class CertificateForm(forms.ModelForm):
    class Meta:
        model = Certificate
        fields = ['consultant', 'valid_until', 'remarks']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields['valid_until'].initial = timezone.now() + timedelta(days=365)
