# Generated manually to register the consultant proxy model for Django.
from __future__ import annotations

from django.db import migrations


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("consultants", "0011_notification_delivered_at_notification_read_at_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="Consultant",
            fields=[],
            options={
                "proxy": True,
                "indexes": [],
                "constraints": [],
            },
            bases=("consultants.consultant",),
        ),
    ]
