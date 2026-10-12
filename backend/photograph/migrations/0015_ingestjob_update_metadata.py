from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("photograph", "0014_storage_device_filesystem_uuid"),
    ]

    operations = [
        migrations.AddField(
            model_name="ingestjob",
            name="update_metadata",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Do not add new catalog entries; refresh missing photograph time "
                    "(EXIF, then filename) and camera model for catalogued files."
                ),
            ),
        ),
    ]
