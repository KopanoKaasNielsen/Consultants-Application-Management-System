from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("consultants", "0015_document"),
    ]

    operations = [
        migrations.AlterField(
            model_name="consultant",
            name="certificate_pdf",
            field=models.FileField(
                blank=True, null=True, upload_to="certificates/signed/"
            ),
        ),
    ]
