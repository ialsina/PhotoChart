import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("photograph", "0008_photograph_photograph__time_a44f56_idx"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="photograph",
            name="photograph__hash_98d696_idx",
        ),
        migrations.RenameField(
            model_name="photograph",
            old_name="hash",
            new_name="checksum",
        ),
        migrations.AddIndex(
            model_name="photograph",
            index=models.Index(
                fields=["checksum"], name="photograph__checksu_a1fce2_idx"
            ),
        ),
        migrations.AlterField(
            model_name="photograph",
            name="checksum",
            field=models.CharField(
                blank=True,
                help_text="Checksum of the photo file (32 hex characters)",
                max_length=32,
                null=True,
                validators=[
                    django.core.validators.RegexValidator(
                        message="Checksum must be a 32-character hexadecimal string",
                        regex="^[a-f0-9]{32}$",
                    )
                ],
            ),
        ),
    ]
