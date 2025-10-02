"""Utilities for generating decision documents as PDFs."""

from __future__ import annotations

import textwrap
from io import BytesIO
from typing import Iterable, Optional

from django.core.files.base import ContentFile
from django.utils import timezone
from PIL import Image, ImageDraw, ImageFont

from apps.consultants.models import Consultant


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

    issued_date = timezone.localdate().strftime("%d %B %Y")
    title = "Consultant Approval Certificate"
    paragraphs = [
        f"This certificate confirms that {consultant.full_name} has been approved as a registered consultant.",
        f"Registration Number: {consultant.registration_number or 'N/A'}",
        f"Issued on {issued_date}.",
    ]
    if generated_by:
        paragraphs.append(f"Processed by {generated_by}.")

    pdf_content = _render_pdf(title, paragraphs)
    filename = f"approval-certificate-{consultant.pk}.pdf"
    consultant.certificate_pdf.save(filename, pdf_content, save=False)
    consultant.certificate_generated_at = timezone.now()
    consultant.save(
        update_fields=[
            "certificate_pdf",
            "certificate_generated_at",
            "rejection_letter",
            "rejection_letter_generated_at",
        ]
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
        ]
    )
    return consultant.rejection_letter
