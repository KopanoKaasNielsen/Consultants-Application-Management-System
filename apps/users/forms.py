"""Form helpers for the users app."""

from django import forms

from apps.users.models import BoardMemberProfile


class BoardSignatureForm(forms.ModelForm):
    """Allow board members to upload their signature image."""

    class Meta:
        model = BoardMemberProfile
        fields = ["signature_image"]
        labels = {"signature_image": "Digital signature"}
        help_texts = {
            "signature_image": "Upload an image of your signature (PNG or JPG).",
        }
        widgets = {
            "signature_image": forms.ClearableFileInput(attrs={"class": "form-control"}),
        }
