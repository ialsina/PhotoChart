from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("photograph", "0012_ingestjob_raw_only"),
    ]

    operations = [
        migrations.AddField(
            model_name="ingestjob",
            name="fix_errors",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Do not add new catalog entries; re-attempt checksum, thumbnail, "
                    "and metadata repair for catalogued files whose photograph has "
                    "has_errors."
                ),
            ),
        ),
    ]
