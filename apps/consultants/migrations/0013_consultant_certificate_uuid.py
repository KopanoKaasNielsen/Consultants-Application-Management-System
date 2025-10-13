import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('consultants', '0012_logentry'),
    ]

    operations = [
        migrations.AddField(
            model_name='consultant',
            name='certificate_uuid',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
