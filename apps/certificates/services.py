"""Utilities for generating decision documents as PDFs."""
from __future__ import annotations

import textwrap
from datetime import timedelta
from io import BytesIO
from typing import Iterable, Optional

from django.core.files.base import ContentFile
from django.utils import timezone
from PIL import Image, ImageDraw, ImageFont

from apps.consultants.models import Consultant
from apps.certificates.models import CertificateRenewal
from consultant_app.certificates import build_verification_url, render_certificate_pdf
from consultant_app.models import Certificate


PAGE_WIDTH = 1654  # approx A4 @ 150dpi
PAGE_HEIGHT = 2339
MARGIN_X = 120
TITLE_Y = 220
LINE_SPACING = 18


def _render_pdf(title: str, paragraphs: Iterable[str]) -> ContentFile:
    """Render a simple one-page PDF with the provided title and body."""
    image = Image.new("RGB", (PAGE_WIDTH, PAGE_HEIGHT), "white")
    draw = ImageDraw.Draw(image)

    title_font = ImageFont.load_default()
    body_font = ImageFont.load_default()

    # Draw the title centered at the top of the page.
    title_bbox = draw.textbbox((0, 0), title, font=title_font)
    title_width = title_bbox[2] - title_bbox[0]
    title_x = (PAGE_WIDTH - title_width) / 2
    draw.text((title_x, TITLE_Y), title, fill="black", font=title_font)

    y = TITLE_Y + 120
    for paragraph in paragraphs:
        if not paragraph:
            y += LINE_SPACING * 2
            continue
        wrapped = textwrap.fill(paragraph, width=80)
        bbox = draw.multiline_textbbox((MARGIN_X, y), wrapped, font=body_font, spacing=LINE_SPACING)
        draw.multiline_text((MARGIN_X, y), wrapped, fill="black", font=body_font, spacing=LINE_SPACING)
        y = bbox[3] + (LINE_SPACING * 2)

    buffer = BytesIO()
    image.save(buffer, format="PDF")
    buffer.seek(0)
    return ContentFile(buffer.read())


CERTIFICATE_VALIDITY_DAYS = 365


def generate_approval_certificate(
    consultant: Consultant, generated_by: Optional[str] = None
):
    """Generate an approval certificate for the consultant and persist it."""
    if consultant.certificate_pdf:
        consultant.certificate_pdf.delete(save=False)

    if consultant.rejection_letter:
        consultant.rejection_letter.delete(save=False)
    consultant.rejection_letter = None
    consultant.rejection_letter_generated_at = None

    issued_at = timezone.now()
    consultant.certificate_generated_at = issued_at
    consultant.certificate_expires_at = timezone.localdate() + timedelta(
        days=CERTIFICATE_VALIDITY_DAYS
    )

    certificate_record, _ = Certificate.objects.get_or_create(
        consultant=consultant,
        issued_at=issued_at,
        defaults={
            "status": Certificate.Status.VALID,
            "status_set_at": issued_at,
            "valid_at": issued_at,
        },
    )
    certificate_record.status = Certificate.Status.VALID
    certificate_record.issued_at = issued_at
    certificate_record.status_set_at = issued_at
    certificate_record.valid_at = issued_at
    certificate_record.revoked_at = None
    certificate_record.expired_at = None
    certificate_record.reissued_at = None
    certificate_record.status_reason = ""
    certificate_record.save(
        update_fields=[
            "status",
            "issued_at",
            "status_set_at",
            "valid_at",
            "revoked_at",
            "expired_at",
            "reissued_at",
            "status_reason",
            "updated_at",
        ]
    )

    for previous in consultant.certificate_records.exclude(pk=certificate_record.pk):
        previous.mark_status(
            Certificate.Status.REISSUED,
            timestamp=issued_at,
            reason=f"Superseded by certificate issued on {issued_at.date().isoformat()}",
        )

    verification_url = build_verification_url(consultant)
    pdf_stream = render_certificate_pdf(
        consultant,
        issued_at=timezone.localdate(),
        verification_url=verification_url,
        generated_by=generated_by,
    )

    filename = f"approval-certificate-{consultant.pk}.pdf"
    consultant.certificate_pdf.save(
        filename, ContentFile(pdf_stream.getvalue()), save=False
    )
    consultant.save(
        update_fields=[
            "certificate_pdf",
            "certificate_generated_at",
            "certificate_expires_at",
            "rejection_letter",
            "rejection_letter_generated_at",
        ]
    )

    pending_renewal = (
        consultant.certificate_renewals.filter(
            status=CertificateRenewal.Status.PENDING
        )
        .order_by("requested_at")
        .last()
    )
    if pending_renewal:
        pending_renewal.status = CertificateRenewal.Status.APPROVED
        pending_renewal.processed_at = timezone.now()
        pending_renewal.processed_by = generated_by or ""
        pending_renewal.save(
            update_fields=["status", "processed_at", "processed_by"]
        )
    return consultant.certificate_pdf


def generate_rejection_letter(
    consultant: Consultant, generated_by: Optional[str] = None
):
    """Generate a rejection letter for the consultant and persist it."""
    if consultant.rejection_letter:
        consultant.rejection_letter.delete(save=False)

    if consultant.certificate_pdf:
        consultant.certificate_pdf.delete(save=False)
    consultant.certificate_pdf = None
    consultant.certificate_generated_at = None
    consultant.certificate_expires_at = None

    issued_date = timezone.localdate().strftime("%d %B %Y")
    title = "Consultant Application Decision"
    paragraphs = [
        f"Dear {consultant.full_name},",
        "We appreciate your interest in registering as a consultant. After careful review, we regret to inform you that your application has not been approved at this time.",
        "You may address the noted concerns and submit a new application in the future.",
        f"Decision issued on {issued_date}.",
    ]
    if generated_by:
        paragraphs.append(f"Reviewed by {generated_by}.")

    pdf_content = _render_pdf(title, paragraphs)
    filename = f"rejection-letter-{consultant.pk}.pdf"
    consultant.rejection_letter.save(filename, pdf_content, save=False)
    consultant.rejection_letter_generated_at = timezone.now()
    consultant.save(
        update_fields=[
            "rejection_letter",
            "rejection_letter_generated_at",
            "certificate_pdf",
            "certificate_generated_at",
            "certificate_expires_at",
        ]
    )

    certificate_record = Certificate.objects.latest_for_consultant(consultant)
    if certificate_record and certificate_record.status != Certificate.Status.REVOKED:
        certificate_record.mark_status(
            Certificate.Status.REVOKED,
            timestamp=timezone.now(),
            reason=f"Revoked when rejection letter issued on {timezone.localdate().isoformat()}",
        )
    return consultant.rejection_letter
