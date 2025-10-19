from django.db import migrations
from django.utils import timezone


STATUS_VALID = "valid"


def seed_certificates(apps, schema_editor):
    Consultant = apps.get_model("consultants", "Consultant")
    Certificate = apps.get_model("consultant_app", "Certificate")

    now = timezone.now()

    certificates = []
    for consultant in Consultant.objects.exclude(certificate_generated_at__isnull=True).iterator():
        issued_at = consultant.certificate_generated_at
        if issued_at is None:
            issued_at = now

        certificate, created = Certificate.objects.get_or_create(
            consultant=consultant,
            issued_at=issued_at,
            defaults={
                "status": STATUS_VALID,
                "status_set_at": issued_at,
                "valid_at": issued_at,
            },
        )

        if not created:
            certificate.status = STATUS_VALID
            certificate.status_set_at = issued_at
            certificate.valid_at = issued_at
            certificate.revoked_at = None
            certificate.expired_at = None
            certificate.reissued_at = None
            certificate.status_reason = ""
            certificate.save(
                update_fields=[
                    "status",
                    "status_set_at",
                    "valid_at",
                    "revoked_at",
                    "expired_at",
                    "reissued_at",
                    "status_reason",
                    "updated_at",
                ]
            )

        certificates.append(certificate.pk)

    if certificates:
        Certificate.objects.filter(pk__in=certificates).update(status_reason="")


def unseed_certificates(apps, schema_editor):
    Certificate = apps.get_model("consultant_app", "Certificate")
    Certificate.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("consultant_app", "0002_certificate"),
    ]

    operations = [
        migrations.RunPython(seed_certificates, unseed_certificates),
    ]
