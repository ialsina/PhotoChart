import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("photograph", "0009_rename_photograph_hash_to_checksum"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="IngestJob",
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
                    "path",
                    models.CharField(
                        help_text=(
                            "Absolute path to ingest.  Must be visible inside the container "
                            "(e.g. /photos/...) or, when INGEST_DOCKER_ENABLED is True, a host "
                            "path that will be bind-mounted into a one-shot container."
                        ),
                        max_length=2048,
                    ),
                ),
                (
                    "mount_root",
                    models.CharField(
                        blank=True,
                        help_text=(
                            "Mount root to bind into the one-shot container (read-only).  "
                            "Leave blank to auto-resolve via findmnt at task execution time.  "
                            "Ignored when path is already visible locally."
                        ),
                        max_length=2048,
                    ),
                ),
                (
                    "device",
                    models.CharField(
                        blank=True,
                        help_text=(
                            "Device label to record in PhotoPath.device instead of the "
                            "auto-detected value.  Useful for giving a stable name to a USB "
                            "drive across remounts."
                        ),
                        max_length=255,
                    ),
                ),
                (
                    "recursive",
                    models.BooleanField(
                        default=True,
                        help_text="Recurse into subdirectories (default True).",
                    ),
                ),
                (
                    "calculate_checksum",
                    models.BooleanField(
                        default=True,
                        help_text="Calculate and store checksums (default True).",
                    ),
                ),
                (
                    "store_images",
                    models.BooleanField(
                        default=True,
                        help_text="Copy thumbnails into the media volume (default True).",
                    ),
                ),
                (
                    "resolution",
                    models.CharField(
                        blank=True,
                        help_text="Optional resolution preset or WxH string for thumbnail storage.",
                        max_length=64,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING", "Pending"),
                            ("RUNNING", "Running"),
                            ("COMPLETED", "Completed"),
                            ("FAILED", "Failed"),
                        ],
                        db_index=True,
                        default="PENDING",
                        max_length=20,
                    ),
                ),
                (
                    "task_id",
                    models.CharField(
                        blank=True,
                        help_text="Celery task ID.",
                        max_length=255,
                    ),
                ),
                (
                    "error",
                    models.TextField(
                        blank=True,
                        help_text="Error message if the job failed.",
                    ),
                ),
                (
                    "count",
                    models.PositiveIntegerField(
                        default=0,
                        help_text="Number of photos ingested.",
                    ),
                ),
                (
                    "checksums_calculated",
                    models.PositiveIntegerField(
                        default=0,
                        help_text="Number of checksums calculated.",
                    ),
                ),
                (
                    "images_stored",
                    models.PositiveIntegerField(
                        default=0,
                        help_text="Number of thumbnails stored in the media volume.",
                    ),
                ),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "requested_by",
                    models.ForeignKey(
                        blank=True,
                        help_text="User who requested this job.",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="ingest_jobs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Ingest Job",
                "verbose_name_plural": "Ingest Jobs",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="ingestjob",
            index=models.Index(
                fields=["status"], name="photograph_ingestjob_status_idx"
            ),
        ),
    ]
