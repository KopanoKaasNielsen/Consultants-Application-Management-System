import logging
from contextlib import suppress
from pathlib import Path

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
    _SIGNATURES = {
        'application/pdf': (b'%PDF',),
        'image/png': (b'\x89PNG\r\n\x1a\n',),
        'image/jpeg': (b'\xff\xd8\xff',),
    }

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

        expected_types = self._expected_content_types(file_obj, content_type)
        if expected_types and not self._has_valid_signature(file_obj, expected_types):
            self.add_error(field, "Only PDF, JPG, or PNG files are allowed.")
            logger.warning(
                "Rejected upload for %s due to invalid signature. Expected one of %s",
                field,
                ", ".join(expected_types),
            )

    def _expected_content_types(self, file_obj, content_type):
        expected = []
        if content_type in self._SIGNATURES:
            expected.append(content_type)

        name = getattr(file_obj, 'name', '')
        if name:
            extension_map = {
                '.pdf': 'application/pdf',
                '.png': 'image/png',
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
            }
            guessed = extension_map.get(Path(name).suffix.lower())
            if guessed and guessed in self._SIGNATURES and guessed not in expected:
                expected.append(guessed)

        return expected

    def _has_valid_signature(self, file_obj, expected_types):
        chunk = self._read_file_signature(file_obj)
        if not chunk:
            return False

        for expected in expected_types:
            for signature in self._SIGNATURES.get(expected, ()):  # pragma: no branch - small list
                if chunk.startswith(signature):
                    return True
        return False

    def _read_file_signature(self, file_obj, size: int = 10) -> bytes:
        file_descriptor = getattr(file_obj, 'file', file_obj)
        needs_close = False
        position = None
        try:
            if hasattr(file_descriptor, 'closed') and getattr(file_descriptor, 'closed'):
                file_descriptor.open("rb")  # type: ignore[call-arg]
                needs_close = True

            if hasattr(file_descriptor, 'tell') and hasattr(file_descriptor, 'seek'):
                position = file_descriptor.tell()

            chunk = file_descriptor.read(size)

            if position is not None and hasattr(file_descriptor, 'seek'):
                file_descriptor.seek(position)
            elif hasattr(file_descriptor, 'seek'):
                file_descriptor.seek(0)

            return chunk or b""
        except Exception:  # pragma: no cover - defensive guard
            logger.exception(
                "Failed to read file signature for %s", getattr(file_obj, 'name', '<unknown>')
            )
            return b""
        finally:
            if needs_close:
                with suppress(Exception):
                    file_descriptor.close()

    class Meta:
        model = Consultant
        exclude = ['user', 'submitted_at', 'status']
        widgets = {
            'dob': forms.DateInput(attrs={'type': 'date'}),
        }
