from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("photograph", "0010_ingestjob"),
    ]

    operations = [
        migrations.AddField(
            model_name="ingestjob",
            name="retry_thumbnails",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Do not add new catalog entries; retry thumbnail storage for "
                    "existing PhotoPath rows when the photograph has no thumbnail."
                ),
            ),
        ),
    ]
