from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("photograph", "0015_ingestjob_update_metadata"),
    ]

    operations = [
        migrations.AlterField(
            model_name="ingestjob",
            name="update_metadata",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Do not add new catalog entries; re-read photograph capture time "
                    "(EXIF, then filename) and camera model from disk for all "
                    "catalogued files under the ingest path and overwrite when sources "
                    "provide values."
                ),
            ),
        ),
        migrations.AddField(
            model_name="ingestjob",
            name="fill_metadata",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Do not add new catalog entries; fill only missing photograph "
                    "capture time (EXIF, then filename) and camera model for "
                    "catalogued files that still lack those fields."
                ),
            ),
        ),
    ]
