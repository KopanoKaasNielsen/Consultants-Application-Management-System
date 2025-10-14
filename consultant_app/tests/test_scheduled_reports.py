from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import override_settings
from django.utils import timezone

from consultant_app.tasks.scheduled_reports import (
    send_admin_report,
    send_weekly_admin_report,
)


@pytest.fixture
def consultant_factory(db):
    from apps.consultants.models import Consultant

    counter = 0

    def factory(**overrides):
        nonlocal counter
        counter += 1
        user_model = get_user_model()
        user = overrides.pop("user", None)
        if user is None:
            user = user_model.objects.create_user(
                username=f"analytics-user-{counter}",
                email=f"analytics{counter}@example.com",
                password="pass1234",
            )

        defaults = {
            "user": user,
            "full_name": overrides.pop("full_name", f"Analytics Consultant {counter}"),
            "id_number": overrides.pop("id_number", f"AN-{counter:03d}"),
            "dob": overrides.pop("dob", timezone.now().date()),
            "gender": overrides.pop("gender", "F"),
            "nationality": overrides.pop("nationality", "Kenya"),
            "email": overrides.pop("email", user.email),
            "phone_number": overrides.pop("phone_number", "0700000000"),
            "business_name": overrides.pop("business_name", f"Analytics Biz {counter}"),
            "registration_number": overrides.pop("registration_number", f"REG-{counter:03d}"),
            "status": overrides.pop("status", "submitted"),
            "submitted_at": overrides.pop("submitted_at", timezone.now()),
            "consultant_type": overrides.pop("consultant_type", "General"),
        }
        defaults.update(overrides)
        return Consultant.objects.create(**defaults)

    return factory


@pytest.mark.django_db
@override_settings(ADMIN_REPORT_RECIPIENTS=("admin@example.com",))
def test_send_admin_report_sends_email_with_attachment(consultant_factory):
    consultant_factory(status="approved")

    mail.outbox = []
    result = send_admin_report("weekly")

    assert result["status"] == "sent"
    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.to == ["admin@example.com"]
    assert message.attachments
    filename, content, mimetype = message.attachments[0]
    assert filename.endswith(".pdf")
    assert mimetype == "application/pdf"
    assert content.startswith(b"%PDF")


@pytest.mark.django_db
@override_settings(ADMIN_REPORT_RECIPIENTS=())
def test_weekly_task_skips_without_recipients(consultant_factory):
    consultant_factory()

    mail.outbox = []
    result = send_weekly_admin_report()

    assert result["status"] == "skipped"
    assert mail.outbox == []


def test_celery_schedule_registers_report_tasks():
    from django.conf import settings

    schedule = getattr(settings, "CELERY_BEAT_SCHEDULE", {})
    assert "consultant_app.send_weekly_admin_report" in schedule
    assert "consultant_app.send_monthly_admin_report" in schedule
