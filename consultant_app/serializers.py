"""Validation helpers for consultant endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from django import forms
from django.utils import timezone

from apps.consultants.models import Consultant
from consultant_app.models import LogEntry


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


@dataclass
class ConsultantDashboardSerializer:
    """Serialize consultant information for the staff dashboard."""

    consultant: Consultant

    #: Mapping of document field names to human friendly labels.
    DOCUMENT_LABELS = {
        "photo": "Photo",
        "id_document": "ID document",
        "cv": "CV",
        "police_clearance": "Police clearance",
        "qualifications": "Qualifications",
        "business_certificate": "Business certificate",
    }

    def _serialize_datetime(self, value):
        if not value:
            return None
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        return value.isoformat()

    def _serialize_date(self, value):
        if not value:
            return None
        return value.isoformat()

    def _missing_documents(self) -> List[str]:
        missing: List[str] = []
        consultant = self.consultant
        for field, label in self.DOCUMENT_LABELS.items():
            if not getattr(consultant, field):
                missing.append(label)
        return missing

    @property
    def data(self) -> Dict[str, Any]:
        consultant = self.consultant
        missing_documents = self._missing_documents()

        return {
            "id": consultant.pk,
            "name": consultant.full_name,
            "email": consultant.email,
            "status": consultant.status,
            "status_display": consultant.get_status_display(),
            "submitted_at": self._serialize_datetime(consultant.submitted_at),
            "updated_at": self._serialize_datetime(consultant.updated_at),
            "certificate_expires_at": self._serialize_date(
                consultant.certificate_expires_at
            ),
            "documents": {
                "is_complete": not missing_documents,
                "missing": missing_documents,
            },
        }


class LogEntrySerializer:
    """Serialize ``LogEntry`` instances for the staff activity feed."""

    def __init__(self, entry: LogEntry):
        self.entry = entry

    def _serialize_timestamp(self):
        timestamp = self.entry.timestamp
        if timezone.is_aware(timestamp):
            timestamp = timezone.localtime(timestamp)
        return timestamp.isoformat()

    @property
    def data(self) -> Dict[str, Any]:
        entry = self.entry
        user_payload: Dict[str, Any] | None = None
        if entry.user_id:
            user = entry.user
            user_payload = {
                "id": entry.user_id,
                "username": user.get_username() if user else None,
                "email": getattr(user, "email", None) if user else None,
            }

        return {
            "id": entry.pk,
            "timestamp": self._serialize_timestamp(),
            "logger": entry.logger_name,
            "level": entry.level,
            "message": entry.message,
            "user": user_payload,
            "context": entry.context or {},
        }
