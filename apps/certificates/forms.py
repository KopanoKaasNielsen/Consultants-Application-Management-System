from django import forms


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
