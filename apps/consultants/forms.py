import logging
from contextlib import suppress

from django import forms
from django.core.files.uploadedfile import UploadedFile
from django.db.models.fields.files import FieldFile

from .models import Consultant

try:  # pragma: no cover - optional dependency in tests
    import magic  # type: ignore
except ImportError:  # pragma: no cover - handled gracefully at runtime
    magic = None

logger = logging.getLogger(__name__)


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

    def _determine_content_type(self, file_obj) -> str | None:
        content_type = getattr(file_obj, 'content_type', None)
        if content_type:
            return content_type

        if hasattr(file_obj, 'file'):
            inner = getattr(file_obj.file, 'content_type', None)
            if inner:
                return inner

        # Attempt to detect using python-magic for better accuracy.
        if magic:
            file_descriptor = getattr(file_obj, 'file', file_obj)
            position = None
            try:
                if hasattr(file_descriptor, 'closed') and getattr(file_descriptor, 'closed'):
                    file_descriptor.open("rb")  # type: ignore[call-arg]
                if hasattr(file_descriptor, 'tell') and hasattr(file_descriptor, 'seek'):
                    position = file_descriptor.tell()
                chunk = file_descriptor.read(4096)
                if position is not None:
                    file_descriptor.seek(position)
                if chunk:
                    with suppress(Exception):
                        return magic.from_buffer(chunk, mime=True)  # type: ignore[arg-type]
            except Exception:  # pragma: no cover - defensive guard
                logger.exception("Failed to detect MIME type for %s", getattr(file_obj, 'name', '<unknown>'))

        if hasattr(file_obj, 'name'):
            from mimetypes import guess_type

            guessed_type, _ = guess_type(file_obj.name)
            return guessed_type

        return None

    def _validate_file(self, field, file_obj):
        try:
            size = file_obj.size
        except Exception:  # pragma: no cover - defensive, should not occur in tests
            size = None

        if size and size > self.MAX_FILE_SIZE:
            self.add_error(field, "File size must be under 2MB.")

        content_type = self._determine_content_type(file_obj)

        if content_type and content_type not in self.ALLOWED_CONTENT_TYPES:
            self.add_error(field, "Only PDF, JPG, or PNG files are allowed.")
            logger.warning(
                "Rejected upload for %s with MIME %s not in %s",
                field,
                content_type,
                ", ".join(self.ALLOWED_CONTENT_TYPES),
            )

    class Meta:
        model = Consultant
        exclude = ['user', 'submitted_at', 'status']
        widgets = {
            'dob': forms.DateInput(attrs={'type': 'date'}),
        }
