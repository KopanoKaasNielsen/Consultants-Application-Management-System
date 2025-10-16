import uuid

from django.db import migrations, models


def generate_unique_certificate_uuids(apps, schema_editor):
    Consultant = apps.get_model('consultants', 'Consultant')

    seen_uuids = set()
    consultants_to_update = []

    for consultant in Consultant.objects.order_by('pk'):
        certificate_uuid = consultant.certificate_uuid

        needs_new_uuid = (
            certificate_uuid is None or certificate_uuid in seen_uuids
        )

        if needs_new_uuid:
            certificate_uuid = uuid.uuid4()

            while certificate_uuid in seen_uuids:
                certificate_uuid = uuid.uuid4()

            consultant.certificate_uuid = certificate_uuid
            consultants_to_update.append(consultant)

        seen_uuids.add(certificate_uuid)

    if consultants_to_update:
        Consultant.objects.bulk_update(consultants_to_update, ['certificate_uuid'])


def noop(apps, schema_editor):
    """No-op reverse migration placeholder."""
    # The migration only generates new UUID values, which we cannot reliably revert.
    # Provide an explicit no-op reverse function to satisfy Django's migration API.
    return


class Migration(migrations.Migration):

    dependencies = [
        ('consultants', '0012_logentry'),
    ]

    operations = [
        migrations.AddField(
            model_name='consultant',
            name='certificate_uuid',
            field=models.UUIDField(default=None, editable=False, null=True),
            preserve_default=False,
        ),
        migrations.RunPython(generate_unique_certificate_uuids, reverse_code=noop),
        migrations.AlterField(
            model_name='consultant',
            name='certificate_uuid',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
