"""Initial schema for consultant-facing models."""

import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone

import apps.consultants.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("security", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Consultant",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("full_name", models.CharField(max_length=255)),
                ("id_number", models.CharField(max_length=50)),
                ("dob", models.DateField()),
                (
                    "gender",
                    models.CharField(
                        choices=[("M", "Male"), ("F", "Female"), ("O", "Other")],
                        max_length=1,
                    ),
                ),
                ("nationality", models.CharField(max_length=100)),
                ("email", models.EmailField(max_length=254)),
                ("phone_number", models.CharField(max_length=20)),
                ("business_name", models.CharField(max_length=255)),
                (
                    "consultant_type",
                    models.CharField(
                        blank=True,
                        db_index=True,
                        help_text="Optional classification used for analytics reporting.",
                        max_length=100,
                        null=True,
                    ),
                ),
                (
                    "registration_number",
                    models.CharField(blank=True, max_length=100, null=True),
                ),
                (
                    "photo",
                    models.ImageField(
                        blank=True,
                        null=True,
                        upload_to="documents/photos/",
                    ),
                ),
                (
                    "id_document",
                    models.FileField(
                        blank=True,
                        null=True,
                        upload_to="documents/id_documents/",
                    ),
                ),
                (
                    "cv",
                    models.FileField(
                        blank=True,
                        null=True,
                        upload_to="documents/cv/",
                    ),
                ),
                (
                    "police_clearance",
                    models.FileField(
                        blank=True,
                        null=True,
                        upload_to="documents/police_clearance/",
                    ),
                ),
                (
                    "qualifications",
                    models.FileField(
                        blank=True,
                        null=True,
                        upload_to="documents/qualifications/",
                    ),
                ),
                (
                    "business_certificate",
                    models.FileField(
                        blank=True,
                        null=True,
                        upload_to="documents/business_certificates/",
                    ),
                ),
                (
                    "certificate_pdf",
                    models.FileField(
                        blank=True, null=True, upload_to="certificates/signed/"
                    ),
                ),
                (
                    "certificate_generated_at",
                    models.DateTimeField(blank=True, null=True),
                ),
                (
                    "certificate_expires_at",
                    models.DateField(blank=True, null=True),
                ),
                (
                    "certificate_uuid",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        unique=True,
                    ),
                ),
                (
                    "rejection_letter",
                    models.FileField(
                        blank=True,
                        null=True,
                        upload_to="documents/rejection_letters/",
                    ),
                ),
                (
                    "rejection_letter_generated_at",
                    models.DateTimeField(blank=True, null=True),
                ),
                (
                    "submitted_at",
                    models.DateTimeField(blank=True, db_index=True, null=True),
                ),
                (
                    "is_seen_by_staff",
                    models.BooleanField(db_index=True, default=False),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "Draft"),
                            ("submitted", "Submitted"),
                            ("incomplete", "Incomplete"),
                            ("vetted", "Vetted"),
                            ("approved", "Approved"),
                            ("rejected", "Rejected"),
                        ],
                        db_index=True,
                        default="draft",
                        max_length=20,
                    ),
                ),
                ("staff_comment", models.TextField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="applications",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("user",),
                        name="consultants_unique_application_per_user",
                    ),
                    models.UniqueConstraint(
                        fields=("id_number",),
                        name="consultants_unique_id_number",
                    ),
                    models.UniqueConstraint(
                        fields=("email", "nationality"),
                        name="consultants_unique_email_per_nationality",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="LogEntry",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "timestamp",
                    models.DateTimeField(auto_now_add=True, db_index=True),
                ),
                (
                    "logger_name",
                    models.CharField(db_index=True, max_length=255),
                ),
                (
                    "level",
                    models.CharField(
                        choices=[
                            ("DEBUG", "Debug"),
                            ("INFO", "Info"),
                            ("WARNING", "Warning"),
                            ("ERROR", "Error"),
                            ("CRITICAL", "Critical"),
                        ],
                        max_length=16,
                    ),
                ),
                ("message", models.TextField()),
                (
                    "context",
                    models.JSONField(blank=True, null=True),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="consultant_logs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ("-timestamp", "-id"),
            },
        ),
        migrations.CreateModel(
            name="Notification",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("message", models.TextField()),
                (
                    "notification_type",
                    models.CharField(
                        choices=[
                            ("approved", "Application approved"),
                            ("rejected", "Application rejected"),
                            ("comment", "New staff comment"),
                        ],
                        max_length=32,
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, db_index=True),
                ),
                (
                    "delivered_at",
                    models.DateTimeField(
                        default=django.utils.timezone.now, editable=False
                    ),
                ),
                ("is_read", models.BooleanField(default=False)),
                ("read_at", models.DateTimeField(blank=True, null=True)),
                (
                    "audit_log",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="notifications",
                        to="security.auditlog",
                    ),
                ),
                (
                    "recipient",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notifications",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ("-created_at", "-id"),
            },
        ),
        migrations.CreateModel(
            name="Document",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "file",
                    models.FileField(
                        max_length=500,
                        upload_to=apps.consultants.models.document_upload_to,
                    ),
                ),
                (
                    "original_name",
                    models.CharField(blank=True, max_length=255),
                ),
                (
                    "content_type",
                    models.CharField(blank=True, max_length=255),
                ),
                ("size", models.PositiveBigIntegerField(default=0)),
                ("uploaded_at", models.DateTimeField(auto_now_add=True)),
                (
                    "application",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="documents",
                        to="consultants.consultant",
                    ),
                ),
                (
                    "uploaded_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="uploaded_documents",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ("-uploaded_at", "-id"),
            },
        ),
    ]
