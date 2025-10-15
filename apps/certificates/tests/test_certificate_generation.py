from __future__ import annotations

import base64
import shutil
import tempfile
from contextlib import ExitStack
from datetime import date, datetime

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.template.loader import render_to_string
from django.test import TestCase, override_settings
from django.utils import timezone
from django.utils.formats import date_format
from PIL import Image
from unittest.mock import patch

from apps.certificates.services import generate_approval_certificate
from apps.consultants.models import Consultant
from apps.security.models import AuditLog
from apps.users.models import BoardMemberProfile


class GenerateApprovalCertificateTests(TestCase):
    """Integration tests for certificate PDF generation and audit logging."""

    def setUp(self) -> None:
        super().setUp()
        self.user_model = get_user_model()
        self.media_root = tempfile.mkdtemp(prefix="certificates-tests-")
        self.addCleanup(shutil.rmtree, self.media_root)
        media_override = override_settings(MEDIA_ROOT=self.media_root)
        media_override.enable()
        self.addCleanup(media_override.disable)

        self.fixed_now = timezone.make_aware(datetime(2024, 1, 1, 15, 30))

        self.board_user = self.user_model.objects.create_user(
            username="board-member",
            email="board.member@example.com",
            password="password123",
            first_name="Board",
            last_name="Reviewer",
        )
        self.generated_by = "Board Reviewer"

        applicant = self.user_model.objects.create_user(
            username="consultant-user",
            email="consultant@example.com",
            password="password123",
        )
        self.consultant = Consultant.objects.create(
            user=applicant,
            full_name="Test Consultant",
            id_number="ID123456",
            dob=date(1990, 1, 1),
            gender="M",
            nationality="Testland",
            email=applicant.email,
            phone_number="0712345678",
            business_name="Consulting LLC",
            status="approved",
        )

    def _signature_file(self) -> SimpleUploadedFile:
        png_bytes = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/"
            "PzAJ/wAAAABJRU5ErkJggg=="
        )
        return SimpleUploadedFile("signature.png", png_bytes, content_type="image/png")

    def _patched_context(self):
        original_render = render_to_string
        captured: dict[str, object] = {"called": 0}

        def capture(template_name, context=None, *args, **kwargs):
            captured["called"] += 1
            captured["template_name"] = template_name
            captured["context"] = dict(context or {})
            result = original_render(template_name, context, *args, **kwargs)
            captured["rendered_html"] = result
            return result

        def fake_write_pdf(self, target=None, *args, **kwargs):
            if target is not None:
                target.write(b"%PDF-1.4 stub\n%%EOF")
            return None

        def fake_qr_code(data, *, box_size=8, border=2):  # noqa: ARG001 - signature defined by patch
            return Image.new("RGB", (20, 20), "white")

        stack = ExitStack()
        stack.enter_context(patch("apps.certificates.services.timezone.now", return_value=self.fixed_now))
        stack.enter_context(
            patch("apps.certificates.services.timezone.localdate", return_value=self.fixed_now.date())
        )
        stack.enter_context(patch("consultant_app.certificates.timezone.now", return_value=self.fixed_now))
        stack.enter_context(
            patch("consultant_app.certificates.timezone.localdate", return_value=self.fixed_now.date())
        )
        stack.enter_context(
            patch("consultant_app.certificates.render_to_string", side_effect=capture)
        )
        stack.enter_context(patch("consultant_app.certificates.HTML.write_pdf", new=fake_write_pdf))
        stack.enter_context(patch("consultant_app.certificates.generate_qr_code", side_effect=fake_qr_code))

        return stack, captured

    def test_generate_certificate_with_signature_image_embeds_signatory_details(self):
        profile = BoardMemberProfile.objects.create(
            user=self.board_user,
            signature_image=self._signature_file(),
        )

        stack, captured = self._patched_context()
        with stack:
            pdf_file = generate_approval_certificate(
                self.consultant,
                generated_by=self.generated_by,
                actor=self.board_user,
            )

        self.assertIsNotNone(pdf_file)
        self.assertEqual(pdf_file.name, self.consultant.certificate_pdf.name)
        self.consultant.refresh_from_db()
        self.assertTrue(self.consultant.certificate_pdf.name.startswith("certificates/signed/"))

        self.assertGreater(captured.get("called", 0), 0)
        context = captured["context"]
        rendered_html = captured["rendered_html"]

        self.assertEqual(context["signer_name"], self.generated_by)
        self.assertEqual(context["signing_datetime"], self.fixed_now)
        self.assertIsNotNone(context["signature_image"])
        self.assertTrue(str(context["signature_image"]).startswith("data:image/png;base64"))
        self.assertIn(str(self.consultant.certificate_uuid), str(context["verification_url"]))

        date_text = date_format(self.fixed_now, "j F Y")
        time_text = date_format(self.fixed_now, "H:i")

        self.assertIn(self.generated_by, rendered_html)
        self.assertIn(f"Signed on {date_text} at {time_text}", rendered_html)
        self.assertIn(str(context["verification_url"]), rendered_html)

        audit_log = AuditLog.objects.filter(
            action_code=AuditLog.ActionCode.CERTIFICATE_ISSUED
        ).latest("timestamp")
        self.assertEqual(audit_log.context.get("signature_asset"), profile.signature_image.name)
        self.assertEqual(audit_log.context.get("signed_at"), self.fixed_now.isoformat())
        self.assertEqual(audit_log.context.get("signatory_user_id"), self.board_user.pk)

    def test_generate_certificate_without_signature_uses_fallback(self):
        BoardMemberProfile.objects.create(user=self.board_user)

        stack, captured = self._patched_context()
        with stack:
            pdf_file = generate_approval_certificate(
                self.consultant,
                generated_by=self.generated_by,
                actor=self.board_user,
            )

        self.assertIsNotNone(pdf_file)
        self.assertEqual(pdf_file.name, self.consultant.certificate_pdf.name)
        self.consultant.refresh_from_db()
        self.assertTrue(self.consultant.certificate_pdf.name.startswith("certificates/signed/"))

        self.assertGreater(captured.get("called", 0), 0)
        context = captured["context"]
        rendered_html = captured["rendered_html"]

        self.assertEqual(context["signer_name"], self.generated_by)
        self.assertEqual(context["signing_datetime"], self.fixed_now)
        self.assertIsNone(context["signature_image"])
        self.assertIn(str(self.consultant.certificate_uuid), str(context["verification_url"]))

        date_text = date_format(self.fixed_now, "j F Y")
        time_text = date_format(self.fixed_now, "H:i")
        self.assertIn(f"Signed on {date_text} at {time_text}", rendered_html)
        self.assertIn(str(context["verification_url"]), rendered_html)

        audit_log = AuditLog.objects.filter(
            action_code=AuditLog.ActionCode.CERTIFICATE_ISSUED
        ).latest("timestamp")
        self.assertNotIn("signature_asset", audit_log.context)
        self.assertNotIn("signed_at", audit_log.context)

