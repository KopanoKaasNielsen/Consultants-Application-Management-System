from django.db import migrations, models
from django.utils import timezone


def add_missing_notification_fields(apps, schema_editor):
    Notification = apps.get_model("consultants", "Notification")
    connection = schema_editor.connection
    table_name = Notification._meta.db_table

    with connection.cursor() as cursor:
        existing_columns = {
            column.name for column in connection.introspection.get_table_description(cursor, table_name)
        }

    if "delivered_at" not in existing_columns:
        field = models.DateTimeField(default=timezone.now, editable=False)
        field.set_attributes_from_name("delivered_at")
        schema_editor.add_field(Notification, field)

    if "read_at" not in existing_columns:
        field = models.DateTimeField(blank=True, null=True)
        field.set_attributes_from_name("read_at")
        schema_editor.add_field(Notification, field)


class Migration(migrations.Migration):
    dependencies = [
        ("consultants", "0016_alter_consultant_certificate_pdf"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(add_missing_notification_fields, migrations.RunPython.noop)
            ],
            state_operations=[
                migrations.AddField(
                    model_name="notification",
                    name="delivered_at",
                    field=models.DateTimeField(default=timezone.now, editable=False),
                ),
                migrations.AddField(
                    model_name="notification",
                    name="read_at",
                    field=models.DateTimeField(blank=True, null=True),
                ),
            ],
        )
    ]
