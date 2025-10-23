from datetime import timedelta

from django import forms
from django.utils import timezone

from .models import Certificate


class CertificateRenewalDecisionForm(forms.Form):
    DECISION_APPROVE = "approve"
    DECISION_DENY = "deny"

    decision = forms.ChoiceField(
        choices=((DECISION_APPROVE, "Approve renewal"), (DECISION_DENY, "Deny renewal"))
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Optional notes to include in the decision log.",
    )


class CertificateForm(forms.ModelForm):
    class Meta:
        model = Certificate
        fields = ["consultant", "valid_until", "remarks"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields["valid_until"].initial = timezone.now() + timedelta(days=365)
