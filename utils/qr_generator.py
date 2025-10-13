"""Utilities for building QR code images for certificate verification."""
from __future__ import annotations

from typing import Final

import qrcode
from PIL import Image

_DEFAULT_ERROR_CORRECTION: Final = qrcode.constants.ERROR_CORRECT_M


def generate_qr_code(data: str, *, box_size: int = 10, border: int = 4) -> Image.Image:
    """Return a QR code image encoding the provided data string."""

    if not isinstance(data, str) or not data:
        raise ValueError("QR code data must be a non-empty string.")

    qr = qrcode.QRCode(
        version=None,
        error_correction=_DEFAULT_ERROR_CORRECTION,
        box_size=box_size,
        border=border,
    )
    qr.add_data(data)
    qr.make(fit=True)

    image = qr.make_image(fill_color="black", back_color="white")
    if not isinstance(image, Image.Image):
        image = image.convert("RGB")

    return image.convert("RGB")


__all__ = ["generate_qr_code"]
