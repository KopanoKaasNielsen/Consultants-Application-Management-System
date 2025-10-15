"""Tests for board member profile helpers and views."""

import tempfile
from io import BytesIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.users.constants import BOARD_COMMITTEE_GROUP_NAME
from apps.users.models import BoardMemberProfile, get_board_signature
from PIL import Image


User = get_user_model()


class BoardMemberProfileHelperTests(TestCase):
    def setUp(self):
        self.group, _ = Group.objects.get_or_create(name=BOARD_COMMITTEE_GROUP_NAME)
        self.user = User.objects.create_user(username="board-helper", password="password123")
        self.user.groups.add(self.group)

    def test_get_board_signature_returns_none_without_profile(self):
        self.assertIsNone(get_board_signature(self.user))

    def test_get_board_signature_returns_file_when_present(self):
        profile = BoardMemberProfile.objects.create(user=self.user)
        profile.signature_image = "board_signatures/sample.png"
        profile.save(update_fields=["signature_image"])

        signature = get_board_signature(self.user)
        self.assertIsNotNone(signature)
        self.assertEqual(signature.name, "board_signatures/sample.png")


@override_settings(MEDIA_ROOT=tempfile.gettempdir())
class BoardMemberProfileViewTests(TestCase):
    def setUp(self):
        self.group, _ = Group.objects.get_or_create(name=BOARD_COMMITTEE_GROUP_NAME)
        self.user = User.objects.create_user(username="board-view", password="password123")
        self.user.groups.add(self.group)

    def test_board_member_can_upload_signature(self):
        self.client.force_login(self.user)

        buffer = BytesIO()
        Image.new("RGB", (2, 1), color="white").save(buffer, format="PNG")

        upload = SimpleUploadedFile(
            "signature.png",
            buffer.getvalue(),
            content_type="image/png",
        )

        response = self.client.post(
            reverse("board_dashboard"),
            {"signature_image": upload},
        )

        self.assertEqual(response.status_code, 302)

        profile = BoardMemberProfile.objects.get(user=self.user)
        self.assertTrue(profile.signature_image.name.endswith("signature.png"))

        profile.signature_image.delete(save=False)
