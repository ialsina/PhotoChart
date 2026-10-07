from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("photograph", "0011_ingestjob_retry_thumbnails"),
    ]

    operations = [
        migrations.AddField(
            model_name="ingestjob",
            name="raw_only",
            field=models.BooleanField(
                default=False,
                help_text="Ingest only RAW image extensions.",
            ),
        ),
    ]
