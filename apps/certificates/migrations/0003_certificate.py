import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
import django.utils.timezone
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("certificates", "0002_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Certificate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("certificate_number", models.CharField(default=uuid.uuid4, max_length=64, unique=True)),
                ("issued_on", models.DateField(default=django.utils.timezone.now)),
                ("valid_until", models.DateField()),
                ("remarks", models.TextField(blank=True, null=True)),
                ("quick_issue", models.BooleanField(default=False)),
                (
                    "consultant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="certificates",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
    ]
