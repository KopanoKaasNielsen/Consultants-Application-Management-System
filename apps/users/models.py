"""Database models and helpers for the users app."""

from __future__ import annotations

from typing import Optional

from django.conf import settings
from django.db import models
from django.db.models.fields.files import FieldFile

from apps.security.models import AuditLog


class BoardMemberProfile(models.Model):
    """Profile metadata for board members."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="board_profile",
    )
    signature_image = models.ImageField(
        upload_to="board_signatures/",
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Board member profile"
        verbose_name_plural = "Board member profiles"

    def __str__(self) -> str:  # pragma: no cover - human-readable helper
        user_display = self.user.get_full_name() or self.user.get_username()
        return f"Board member profile for {user_display}"


def get_board_signature(user) -> Optional[FieldFile]:
    """Return the stored signature for the given user, if any."""

    if not user:
        return None

    profile: Optional[BoardMemberProfile]
    try:
        profile = user.board_profile
    except (AttributeError, BoardMemberProfile.DoesNotExist):  # type: ignore[attr-defined]
        return None

    if not profile or not profile.signature_image:
        return None

    return profile.signature_image


__all__ = ["AuditLog", "BoardMemberProfile", "get_board_signature"]
