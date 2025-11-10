"""Initial database schema for the ``apps.security`` application."""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AuditLog",
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
                    "resolved_role",
                    models.CharField(blank=True, max_length=32),
                ),
                (
                    "action_code",
                    models.CharField(choices=[
                        ("view_consultant", "Viewed consultant"),
                        ("export_pdf", "Exported consultant PDF"),
                        ("export_bulk_pdf", "Exported bulk consultant PDF"),
                        ("export_csv", "Exported consultant CSV"),
                        ("approve_application", "Approved application"),
                        ("reject_application", "Rejected application"),
                        ("request_info", "Requested more information"),
                        ("send_analytics_report", "Sent analytics report"),
                        ("create_user", "Created user"),
                        ("certificate_issued", "Issued consultant certificate"),
                        ("certificate_revoked", "Revoked consultant certificate"),
                        ("login_success", "Successful login"),
                        ("login_failure", "Failed login"),
                        ("upload_document", "Uploaded supporting document"),
                        ("delete_document", "Deleted supporting document"),
                    ], max_length=64),
                ),
                ("target", models.CharField(blank=True, max_length=255)),
                ("endpoint", models.CharField(blank=True, max_length=255)),
                (
                    "client_ip",
                    models.GenericIPAddressField(blank=True, null=True),
                ),
                (
                    "timestamp",
                    models.DateTimeField(auto_now_add=True, db_index=True),
                ),
                (
                    "context",
                    models.JSONField(blank=True, default=dict),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="security_audit_logs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ("-timestamp", "-id"),
            },
        ),
    ]
