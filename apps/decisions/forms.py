from django import forms
from .models import ApplicationAction

class ActionForm(forms.ModelForm):
    class Meta:
        model = ApplicationAction
        fields = ['action', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 4}),
        }
