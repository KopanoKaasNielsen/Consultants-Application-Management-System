from datetime import date
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.consultants.models import Consultant


def _generate_png_bytes() -> bytes:
    image = Image.new("RGB", (1, 1), color="white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


PNG_IMAGE_BYTES = _generate_png_bytes()
PDF_BYTES = b"%PDF-1.4 test pdf content"


def consultant_form_data(action="submit", **overrides):
    data = {
        "full_name": "Test Consultant",
        "id_number": "ID123456",
        "dob": "1990-01-01",
        "gender": "M",
        "nationality": "Testland",
        "email": "consultant@example.com",
        "phone_number": "+1234567890",
        "business_name": "Test Consulting LLC",
        "registration_number": "REG123",
        "action": action,
    }
    data.update(overrides)
    return data


def consultant_form_files(**overrides):
    files = {
        "photo": SimpleUploadedFile(
            "photo.png", PNG_IMAGE_BYTES, content_type="image/png"
        ),
        "id_document": SimpleUploadedFile(
            "id.pdf", PDF_BYTES, content_type="application/pdf"
        ),
        "cv": SimpleUploadedFile("cv.pdf", PDF_BYTES, content_type="application/pdf"),
        "police_clearance": SimpleUploadedFile(
            "police.pdf", PDF_BYTES, content_type="application/pdf"
        ),
        "qualifications": SimpleUploadedFile(
            "qualifications.pdf", PDF_BYTES, content_type="application/pdf"
        ),
        "business_certificate": SimpleUploadedFile(
            "business.pdf", PDF_BYTES, content_type="application/pdf"
        ),
    }
    files.update(overrides)
    return files


def create_consultant_instance(user, **overrides):
    defaults = {
        "user": user,
        "full_name": "Existing Consultant",
        "id_number": "ID987654",
        "dob": date(1985, 5, 1),
        "gender": "M",
        "nationality": "Testland",
        "email": "existing@example.com",
        "phone_number": "+1987654321",
        "business_name": "Existing Consulting Ltd",
        "registration_number": "REG999",
    }
    defaults.update(overrides)
    return Consultant.objects.create(**defaults)
