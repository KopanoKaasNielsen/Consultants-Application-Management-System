"""Validation helpers for consultant endpoints."""

from __future__ import annotations

from typing import Any, Dict

from django import forms

from apps.consultants.models import Consultant


class ConsultantValidationSerializer(forms.Form):
    """Validate consultant uniqueness constraints via JSON payload."""

    email = forms.EmailField(required=False)
    nationality = forms.CharField(required=False)
    id_number = forms.CharField(required=False)
    registration_number = forms.CharField(required=False)
    consultant_id = forms.IntegerField(required=False, min_value=1)

    error_messages = {
        "duplicate_email": "A consultant with this email already exists.",
        "duplicate_id": "A consultant with this ID number already exists.",
        "duplicate_registration": "A consultant with this registration number already exists.",
    }

    def clean(self) -> Dict[str, Any]:  # type: ignore[override]
        cleaned = super().clean()
        consultant_id = cleaned.get("consultant_id")

        def exclude_current(queryset):
            if consultant_id:
                return queryset.exclude(pk=consultant_id)
            return queryset

        errors: Dict[str, str] = {}

        email = cleaned.get("email")
        nationality = cleaned.get("nationality")
        if email:
            queryset = Consultant.objects.filter(email__iexact=email)
            if nationality:
                queryset = queryset.filter(nationality__iexact=nationality)
            if exclude_current(queryset).exists():
                errors["email"] = self.error_messages["duplicate_email"]

        id_number = cleaned.get("id_number")
        if id_number:
            queryset = Consultant.objects.filter(id_number__iexact=id_number)
            if exclude_current(queryset).exists():
                errors["id_number"] = self.error_messages["duplicate_id"]

        registration_number = cleaned.get("registration_number") or None
        if registration_number:
            queryset = Consultant.objects.filter(
                registration_number__iexact=registration_number
            )
            if exclude_current(queryset).exists():
                errors["registration_number"] = self.error_messages[
                    "duplicate_registration"
                ]

        if errors:
            raise forms.ValidationError(errors)

        return cleaned
