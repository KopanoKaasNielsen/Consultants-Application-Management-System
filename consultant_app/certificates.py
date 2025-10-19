"""Helpers for generating and validating consultant certificates."""
from __future__ import annotations

import base64
import logging
import mimetypes
import os
from dataclasses import dataclass
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Final, Optional
from urllib.parse import urlencode

from django.conf import settings
from django.core import signing
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from weasyprint import HTML

from apps.consultants.models import Consultant
from consultant_app.models import Certificate

from utils.qr_generator import generate_qr_code

_TOKEN_SALT: Final = "consultant_app.certificates.token"

logger = logging.getLogger(__name__)


class CertificateTokenError(Exception):
    """Raised when a certificate token cannot be validated."""


@dataclass(frozen=True)
class CertificateMetadata:
    """Verification metadata decoded from a certificate token."""

    consultant_id: int
    issued_at: str


def _issued_at_to_date(value: str) -> date | None:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:  # pragma: no cover - guarded by token issuer
        return None
    return parsed.date()


def _certificate_for_consultant(consultant: Consultant) -> Certificate | None:
    if not consultant.certificate_generated_at:
        return None

    issued_at_iso = consultant.certificate_generated_at.isoformat()
    certificate = Certificate.objects.matching_issue_timestamp(
        consultant, issued_at_iso
    )
    if certificate:
        return certificate

    return Certificate.objects.active_for_consultant(consultant)


def build_certificate_token(consultant: Consultant) -> str:
    """Create a signed token tied to the consultant's active certificate."""

    if not consultant.pk:
        raise ValueError("Consultant must be saved before issuing a certificate.")

    certificate = _certificate_for_consultant(consultant)
    if not certificate or not certificate.issued_at:
        raise ValueError("Certificate issue timestamp is required to build a token.")

    if not certificate.is_active:
        raise ValueError("Certificate is not currently valid.")

    payload = {
        "consultant_id": consultant.pk,
        "issued_at": certificate.issued_at.isoformat(),
    }

    return signing.dumps(payload, salt=_TOKEN_SALT)


def verify_certificate_token(token: str, consultant: Consultant) -> CertificateMetadata:
    """Validate the token and return the certificate metadata."""

    if not token:
        raise CertificateTokenError("Missing verification token.")

    try:
        payload = signing.loads(token, salt=_TOKEN_SALT)
    except signing.BadSignature as exc:
        logger.warning(
            "Invalid certificate token provided for consultant %s", consultant.pk, exc_info=exc
        )
        raise CertificateTokenError("Invalid Certificate") from exc

    if payload.get("consultant_id") != consultant.pk:
        raise CertificateTokenError("Token does not match the requested certificate.")

    issued_at = payload.get("issued_at")
    if not issued_at:
        raise CertificateTokenError("Certificate is not currently active.")

    certificate = Certificate.objects.matching_issue_timestamp(consultant, issued_at)
    if not certificate or not certificate.issued_at:
        raise CertificateTokenError("Certificate is not currently active.")

    if issued_at != certificate.issued_at.isoformat():
        raise CertificateTokenError("Token is no longer valid for this certificate.")

    invalid_status_errors = {
        Certificate.Status.REVOKED: "Certificate has been revoked.",
        Certificate.Status.EXPIRED: "Certificate has expired.",
        Certificate.Status.REISSUED: "Token is no longer valid for this certificate.",
    }

    error_message = invalid_status_errors.get(certificate.status)
    if error_message:
        raise CertificateTokenError(error_message)

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


def _image_to_data_uri(image: object | None) -> str | None:
    """Return a data URI for the provided image-like object, when possible."""

    if not image:
        return None

    if isinstance(image, str):
        if image.startswith("data:") or image.startswith("http") or image.startswith("file:"):
            return image

        potential_path = Path(image)
        if not potential_path.is_absolute():
            media_root = getattr(settings, "MEDIA_ROOT", "")
            if media_root:
                potential_path = Path(media_root) / image

        if potential_path.exists():
            data = potential_path.read_bytes()
            mime, _ = mimetypes.guess_type(potential_path.name)
            mime = mime or "image/png"
            encoded = base64.b64encode(data).decode("ascii")
            return f"data:{mime};base64,{encoded}"

        return image

    file_path = getattr(image, "path", None)
    if file_path and os.path.exists(file_path):
        data = Path(file_path).read_bytes()
        mime, _ = mimetypes.guess_type(file_path)
        mime = mime or "image/png"
        encoded = base64.b64encode(data).decode("ascii")
        return f"data:{mime};base64,{encoded}"

    if hasattr(image, "read"):
        try:
            data = image.read()
        finally:
            if hasattr(image, "seek"):
                image.seek(0)
        if not data:
            return None
        mime = mimetypes.guess_type(getattr(image, "name", ""))[0] or "image/png"
        encoded = base64.b64encode(data).decode("ascii")
        return f"data:{mime};base64,{encoded}"

    url = getattr(image, "url", None)
    if url:
        return url

    return None


def render_certificate_pdf(
    consultant: Consultant,
    *,
    issued_at: date,
    verification_url: str,
    generated_by: Optional[str] = None,
    signature_image: object | None = None,
    signing_datetime: Optional[datetime] = None,
    request: Optional[object] = None,
) -> BytesIO:
    """Render the certificate PDF bytes including a QR code."""

    qr_image = generate_qr_code(verification_url, box_size=8, border=2)
    qr_buffer = BytesIO()
    qr_image.save(qr_buffer, format="PNG")
    qr_data_uri = "data:image/png;base64," + base64.b64encode(qr_buffer.getvalue()).decode(
        "ascii"
    )

    signer_name = generated_by or ""
    signing_time = signing_datetime or timezone.now()

    context = {
        "consultant": consultant,
        "issued_at": issued_at,
        "verification_url": verification_url,
        "qr_code_data_uri": qr_data_uri,
        "signer_name": signer_name,
        "signing_datetime": signing_time,
        "signature_image": _image_to_data_uri(signature_image),
    }

    rendered_html = render_to_string("certificate_template.html", context)

    base_url = getattr(settings, "MEDIA_ROOT", "") or (
        request.build_absolute_uri("/") if request else None
    )

    buffer = BytesIO()
    HTML(string=rendered_html, base_url=base_url).write_pdf(target=buffer)
    buffer.seek(0)
    return buffer


def update_certificate_status(
    consultant: Consultant,
    *,
    status: Certificate.Status | str,
    user: Any | None = None,
    reason: str | None = None,
    timestamp: datetime | None = None,
    context: dict[str, Any] | None = None,
) -> Certificate | None:
    """Apply a certificate status transition with logging and bookkeeping."""

    try:
        status_choice = Certificate.Status(status)
    except ValueError as exc:  # pragma: no cover - guarded by callers/tests
        raise ValueError(f"Unsupported certificate status: {status}") from exc

    reason_text = (reason or "").strip()
    applied_at = timestamp or timezone.now()
    actor_id = getattr(user, "pk", None)

    certificate = Certificate.objects.latest_for_consultant(consultant)
    if not certificate:
        log_context: dict[str, Any] = {
            "action": "certificate.status.missing",
            "consultant_id": consultant.pk,
            "requested_status": status_choice.value,
            "reason": reason_text,
            "applied_at": applied_at,
        }
        if context:
            log_context.update(context)
        logger.warning(
            "No certificate record available for consultant %s", consultant.pk,
            extra={
                "user_id": actor_id,
                "consultant_id": consultant.pk,
                "context": log_context,
            },
        )
        return None

    previous_status = certificate.status
    certificate.mark_status(
        status_choice.value,
        reason=reason_text,
        timestamp=applied_at,
    )

    log_context = {
        "action": f"certificate.status.{status_choice.value}",
        "consultant_id": consultant.pk,
        "certificate_id": certificate.pk,
        "previous_status": previous_status,
        "new_status": certificate.status,
        "reason": reason_text,
        "applied_at": applied_at,
    }
    if context:
        log_context.update(context)

    logger.info(
        "Set consultant %s certificate %s to %s",
        consultant.pk,
        certificate.pk,
        status_choice.label,
        extra={
            "user_id": actor_id,
            "consultant_id": consultant.pk,
            "context": log_context,
        },
    )

    return certificate


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
    "update_certificate_status",
    "verify_certificate_token",
]
