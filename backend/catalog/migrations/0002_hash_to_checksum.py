from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0001_initial"),
    ]

    operations = [
        migrations.RenameField(
            model_name="hash",
            old_name="hash",
            new_name="checksum",
        ),
        migrations.RenameModel(
            old_name="Hash",
            new_name="Checksum",
        ),
    ]
