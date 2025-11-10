"""Initial schema for the ``consultant_app`` application."""

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("consultants", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Certificate",
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
                    "status",
                    models.CharField(
                        choices=[
                            ("valid", "Valid"),
                            ("revoked", "Revoked"),
                            ("expired", "Expired"),
                            ("reissued", "Reissued"),
                        ],
                        db_index=True,
                        default="valid",
                        max_length=16,
                    ),
                ),
                (
                    "issued_at",
                    models.DateTimeField(
                        blank=True,
                        help_text="Timestamp when the certificate was issued.",
                        null=True,
                    ),
                ),
                (
                    "status_set_at",
                    models.DateTimeField(
                        default=django.utils.timezone.now,
                        help_text="Timestamp when the current status was applied.",
                    ),
                ),
                (
                    "valid_at",
                    models.DateTimeField(
                        blank=True,
                        help_text="Timestamp when the certificate became valid.",
                        null=True,
                    ),
                ),
                (
                    "revoked_at",
                    models.DateTimeField(
                        blank=True,
                        help_text="Timestamp when the certificate was revoked.",
                        null=True,
                    ),
                ),
                (
                    "expired_at",
                    models.DateTimeField(
                        blank=True,
                        help_text="Timestamp when the certificate expired.",
                        null=True,
                    ),
                ),
                (
                    "reissued_at",
                    models.DateTimeField(
                        blank=True,
                        help_text="Timestamp when the certificate was superseded by a new issue.",
                        null=True,
                    ),
                ),
                (
                    "status_reason",
                    models.TextField(
                        blank=True,
                        help_text="Optional reason describing why the status was applied.",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "consultant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="certificate_records",
                        to="consultants.consultant",
                    ),
                ),
            ],
            options={
                "ordering": ("-issued_at", "-status_set_at", "-pk"),
                "verbose_name": "Consultant certificate",
                "verbose_name_plural": "Consultant certificates",
            },
        ),
    ]
