from django.db import models


def default_media_extensions():
    return [
        ".jpg",
        ".jpeg",
        ".heic",
        ".heif",
        ".png",
        ".tif",
        ".tiff",
        ".nef",
        ".dng",
        ".mp4",
        ".mov",
        ".m4v",
    ]


def default_date_priority():
    return [
        "DateTimeOriginal",
        "SubSecDateTimeOriginal",
        "CreateDate",
        "MediaCreateDate",
        "TrackCreateDate",
        "ModifyDate",
    ]


def default_stability():
    return {"interval_seconds": 30, "checks": 2}


def default_retry():
    return {"attempts": 4, "initial_seconds": 5, "multiplier": 3}


class OrganizerConfiguration(models.Model):
    name = models.CharField(max_length=255, unique=True)
    adapter = models.CharField(max_length=50, default="local")
    source = models.TextField()
    destination = models.TextField()
    pattern = models.CharField(max_length=255, default="%Y/%YQ%Q/%Y%M%D")
    quarantine = models.TextField(null=True, blank=True)
    mode = models.CharField(
        max_length=10, choices=[("copy", "Copy"), ("move", "Move")], default="move"
    )
    adapter_options = models.JSONField(
        default=dict,
        blank=True,
        help_text="Non-secret options and names of environment variables containing secrets",
    )
    timezone = models.CharField(max_length=64, default="UTC")
    collision = models.CharField(
        max_length=20,
        choices=[
            ("suffix", "Suffix"),
            ("fail", "Fail"),
            ("quarantine", "Quarantine"),
        ],
        default="suffix",
    )
    duplicate_detection = models.CharField(max_length=30, default="size_then_hash")
    workers = models.PositiveSmallIntegerField(default=1)
    scan_interval_seconds = models.FloatField(default=60)
    process_after = models.DateTimeField(null=True, blank=True)
    include_first = models.BooleanField(default=True)
    day_starts_at = models.FloatField(default=0)
    media_extensions = models.JSONField(default=default_media_extensions)
    date_priority = models.JSONField(default=default_date_priority)
    stability = models.JSONField(default=default_stability)
    retry = models.JSONField(default=default_retry)
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        permissions = [
            ("operate_organizer", "Can run destructive PhotoChart operations"),
        ]

    def __str__(self):
        return self.name


class OrganizerJob(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        RUNNING = "RUNNING", "Running"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"

    configuration = models.ForeignKey(
        OrganizerConfiguration, on_delete=models.PROTECT, related_name="jobs"
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    dry_run = models.BooleanField(default=True)
    error = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class OrganizerOperation(models.Model):
    job = models.ForeignKey(
        OrganizerJob, on_delete=models.CASCADE, related_name="operations"
    )
    status = models.CharField(max_length=30)
    source = models.TextField()
    destination = models.TextField(null=True, blank=True)
    object_id = models.CharField(max_length=512, blank=True)
    capture_date = models.DateTimeField(null=True, blank=True)
    date_source = models.CharField(max_length=255, blank=True)
    detail = models.TextField(blank=True)
    verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["source"]),
        ]


class DuplicateGroup(models.Model):
    checksum = models.CharField(max_length=64, db_index=True)
    size = models.BigIntegerField()
    paths = models.JSONField(default=list)
    wasted_bytes = models.BigIntegerField(default=0)
    scanned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-wasted_bytes"]
