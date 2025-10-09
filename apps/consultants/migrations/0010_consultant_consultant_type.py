from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("consultants", "0009_consultant_is_seen_by_staff"),
    ]

    operations = [
        migrations.AddField(
            model_name="consultant",
            name="consultant_type",
            field=models.CharField(
                blank=True,
                help_text="Optional classification used for analytics reporting.",
                max_length=100,
                null=True,
                db_index=True,
            ),
        ),
    ]
