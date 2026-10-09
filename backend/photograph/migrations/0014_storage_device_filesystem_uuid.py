# Generated manually for storage device identification

import hashlib

from django.db import migrations, models
import django.db.models.deletion


def backfill_filesystem_uuid(apps, schema_editor):
    PhotoPath = apps.get_model("photograph", "PhotoPath")
    StorageDevice = apps.get_model("photograph", "StorageDevice")

    device_to_uuid: dict[str, str] = {}
    for row in PhotoPath.objects.values("device").distinct():
        dev = row["device"]
        digest = hashlib.sha256(dev.encode("utf-8")).hexdigest()[:32]
        device_to_uuid[dev] = f"photchart:legacy:{digest}"

    sd_by_uuid: dict[str, int] = {}
    for dev, fs_uuid in device_to_uuid.items():
        sd, _ = StorageDevice.objects.get_or_create(
            filesystem_uuid=fs_uuid,
            defaults={
                "catalog_device": dev,
                "probe_notes": "legacy_migration",
            },
        )
        sd_by_uuid[fs_uuid] = sd.pk

    for pp in PhotoPath.objects.iterator():
        fs_uuid = device_to_uuid[pp.device]
        pp.filesystem_uuid = fs_uuid
        pp.storage_device_id = sd_by_uuid[fs_uuid]
        pp.save(update_fields=["filesystem_uuid", "storage_device_id"])


class Migration(migrations.Migration):

    dependencies = [
        ("photograph", "0013_ingestjob_fix_errors"),
    ]

    operations = [
        migrations.CreateModel(
            name="StorageDevice",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "filesystem_uuid",
                    models.CharField(
                        help_text="Canonical volume id (OS UUID or photchart:synthetic)",
                        max_length=80,
                        unique=True,
                    ),
                ),
                (
                    "catalog_device",
                    models.CharField(
                        blank=True,
                        db_index=True,
                        help_text="Last seen PhotoPath.device label for this volume",
                        max_length=255,
                        null=True,
                    ),
                ),
                (
                    "capacity_bytes",
                    models.BigIntegerField(
                        blank=True,
                        help_text="Filesystem total size in bytes",
                        null=True,
                    ),
                ),
                ("vendor", models.CharField(blank=True, max_length=255, null=True)),
                ("model", models.CharField(blank=True, max_length=255, null=True)),
                ("serial", models.CharField(blank=True, max_length=255, null=True)),
                ("source", models.CharField(blank=True, max_length=512, null=True)),
                ("fstype", models.CharField(blank=True, max_length=64, null=True)),
                (
                    "mount_root",
                    models.CharField(blank=True, max_length=2048, null=True),
                ),
                ("probed_at", models.DateTimeField(blank=True, null=True)),
                ("probe_notes", models.TextField(blank=True, default="")),
            ],
            options={
                "verbose_name": "Storage Device",
                "verbose_name_plural": "Storage Devices",
            },
        ),
        migrations.AddField(
            model_name="photopath",
            name="filesystem_uuid",
            field=models.CharField(
                help_text="Volume identity for catalog uniqueness (OS UUID or synthetic)",
                max_length=80,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="photopath",
            name="storage_device",
            field=models.ForeignKey(
                blank=True,
                help_text="Linked volume metadata",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="paths",
                to="photograph.storagedevice",
            ),
        ),
        migrations.AddField(
            model_name="ingestjob",
            name="update_device",
            field=models.BooleanField(
                default=False,
                help_text="Re-probe and refresh StorageDevice metadata for the ingested volume.",
            ),
        ),
        migrations.RunPython(backfill_filesystem_uuid, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="photopath",
            name="filesystem_uuid",
            field=models.CharField(
                help_text="Volume identity for catalog uniqueness (OS UUID or synthetic)",
                max_length=80,
            ),
        ),
        migrations.AlterUniqueTogether(
            name="photopath",
            unique_together=set(),
        ),
        migrations.AddIndex(
            model_name="photopath",
            index=models.Index(
                fields=["filesystem_uuid"], name="photograph_p_filesys_6f0a2a_idx"
            ),
        ),
        migrations.AddConstraint(
            model_name="photopath",
            constraint=models.UniqueConstraint(
                fields=("path", "filesystem_uuid"),
                name="photopath_path_filesystem_uuid_uniq",
            ),
        ),
    ]
