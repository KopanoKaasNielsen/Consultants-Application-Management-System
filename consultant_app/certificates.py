"""Helpers for generating and validating consultant certificates."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from io import BytesIO
from typing import Final, Optional
from urllib.parse import urlencode

from django.conf import settings
from django.core import signing
from django.urls import reverse
from PIL import Image, ImageDraw, ImageFont

from apps.consultants.models import Consultant

from utils.qr_generator import generate_qr_code

# Layout constants for the generated PDF document.
PAGE_WIDTH: Final = 1654
PAGE_HEIGHT: Final = 2339
MARGIN_X: Final = 120
TITLE_Y: Final = 220
LINE_SPACING: Final = 18
QR_SIZE: Final = 420
QR_MARGIN_BOTTOM: Final = 180

_TOKEN_SALT: Final = "consultant_app.certificates.token"


class CertificateTokenError(Exception):
    """Raised when a certificate token cannot be validated."""


@dataclass(frozen=True)
class CertificateMetadata:
    """Verification metadata decoded from a certificate token."""

    consultant_id: int
    issued_at: str


def _format_date(value: date | None) -> str:
    if not value:
        return "N/A"
    return value.strftime("%d %B %Y")


def _issued_at_to_date(value: str) -> date | None:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:  # pragma: no cover - guarded by token issuer
        return None
    return parsed.date()


def build_certificate_token(consultant: Consultant) -> str:
    """Create a signed token tied to the consultant's active certificate."""

    if not consultant.pk:
        raise ValueError("Consultant must be saved before issuing a certificate.")

    if not consultant.certificate_generated_at:
        raise ValueError("Certificate issue timestamp is required to build a token.")

    payload = {
        "consultant_id": consultant.pk,
        "issued_at": consultant.certificate_generated_at.isoformat(),
    }

    return signing.dumps(payload, salt=_TOKEN_SALT)


def verify_certificate_token(token: str, consultant: Consultant) -> CertificateMetadata:
    """Validate the token and return the certificate metadata."""

    if not token:
        raise CertificateTokenError("Missing verification token.")

    try:
        payload = signing.loads(token, salt=_TOKEN_SALT)
    except signing.BadSignature as exc:
        raise CertificateTokenError("Invalid or tampered verification token.") from exc

    if payload.get("consultant_id") != consultant.pk:
        raise CertificateTokenError("Token does not match the requested certificate.")

    issued_at = payload.get("issued_at")
    if not issued_at or not consultant.certificate_generated_at:
        raise CertificateTokenError("Certificate is not currently active.")

    if issued_at != consultant.certificate_generated_at.isoformat():
        raise CertificateTokenError("Token is no longer valid for this certificate.")

    return CertificateMetadata(consultant_id=consultant.pk, issued_at=issued_at)


def build_verification_url(consultant: Consultant) -> str:
    """Return the URL embedded in the QR code for certificate verification."""

    token = build_certificate_token(consultant)
    path = reverse(
        "consultant-certificate-verify",
        kwargs={"certificate_uuid": consultant.certificate_uuid},
    )

    base_url = getattr(settings, "CERTIFICATE_VERIFY_BASE_URL", "")
    if base_url:
        base_url = base_url.rstrip("/")

    query = urlencode({"token": token})
    if base_url:
        return f"{base_url}{path}?{query}"
    return f"{path}?{query}"


def _load_font() -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype("arial.ttf", 24)
    except (OSError, IOError):  # pragma: no cover - fallback depends on runtime fonts
        return ImageFont.load_default()


def render_certificate_pdf(
    consultant: Consultant,
    *,
    issued_at: date,
    verification_url: str,
    generated_by: Optional[str] = None,
) -> BytesIO:
    """Render the certificate PDF bytes including a QR code."""

    image = Image.new("RGB", (PAGE_WIDTH, PAGE_HEIGHT), "white")
    draw = ImageDraw.Draw(image)

    title_font = _load_font()
    body_font = ImageFont.load_default()

    title = "Consultant Approval Certificate"
    title_bbox = draw.textbbox((0, 0), title, font=title_font)
    title_width = title_bbox[2] - title_bbox[0]
    title_x = (PAGE_WIDTH - title_width) / 2
    draw.text((title_x, TITLE_Y), title, fill="black", font=title_font)

    paragraphs = [
        f"This certifies that {consultant.full_name} has been approved as a registered consultant.",
        f"Registration Number: {consultant.registration_number or 'N/A'}",
        f"Issued on {_format_date(issued_at)}.",
    ]

    if consultant.certificate_expires_at:
        paragraphs.append(
            f"Certificate valid until {_format_date(consultant.certificate_expires_at)}."
        )

    if generated_by:
        paragraphs.append(f"Processed by {generated_by}.")

    paragraphs.append("Scan the QR code or visit the link below to verify this certificate.")
    paragraphs.append(verification_url)

    y = TITLE_Y + 140
    for paragraph in paragraphs:
        draw.multiline_text(
            (MARGIN_X, y),
            paragraph,
            fill="black",
            font=body_font,
            spacing=LINE_SPACING,
        )
        paragraph_bbox = draw.multiline_textbbox(
            (MARGIN_X, y), paragraph, font=body_font, spacing=LINE_SPACING
        )
        y = paragraph_bbox[3] + (LINE_SPACING * 2)

    qr_image = generate_qr_code(verification_url, box_size=8, border=2)
    qr_image = qr_image.resize((QR_SIZE, QR_SIZE), Image.NEAREST)

    qr_x = PAGE_WIDTH - MARGIN_X - QR_SIZE
    qr_y = PAGE_HEIGHT - QR_SIZE - QR_MARGIN_BOTTOM
    image.paste(qr_image, (qr_x, qr_y))

    buffer = BytesIO()
    image.save(buffer, format="PDF")
    buffer.seek(0)
    return buffer


def decode_certificate_metadata(token: str, consultant: Consultant) -> dict[str, object]:
    """Return structured details for verified certificates."""

    metadata = verify_certificate_token(token, consultant)
    issued_on = _issued_at_to_date(metadata.issued_at)
    return {
        "consultant": consultant,
        "issued_on": issued_on,
        "metadata": metadata,
    }


__all__ = [
    "CertificateMetadata",
    "CertificateTokenError",
    "build_certificate_token",
    "build_verification_url",
    "decode_certificate_metadata",
    "render_certificate_pdf",
    "verify_certificate_token",
]
