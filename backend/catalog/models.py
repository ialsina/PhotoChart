"""Photo catalog management system - Django models.

This module provides Django models for managing photo collections.
It handles photo metadata, directory organization, and provides functionality for
finding duplicates and managing photo locations.

The models correspond to the original SQLite schema:
- Hash: File paths and their MD5 hashes
- Directories: Directory paths and metadata
- DirKinds: Directory type definitions
- TimeLoc: Timestamp and location data
- Locations: Location definitions
"""

from django.db import models
from django.core.validators import RegexValidator


class DirKind(models.Model):
    """Directory type definitions.

    Represents different kinds/categories of directories (e.g., "LOCAL", "BACKUP", etc.).
    """

    name = models.CharField(
        max_length=255,
        unique=True,
        help_text="Directory kind name (e.g., 'LOCAL', 'BACKUP')",
    )

    class Meta:
        db_table = "DirKinds"
        verbose_name = "Directory Kind"
        verbose_name_plural = "Directory Kinds"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Location(models.Model):
    """Location definitions.

    Represents geographic or logical locations for photo organization.
    """

    name = models.CharField(max_length=255, unique=True, help_text="Location name")

    class Meta:
        db_table = "Locations"
        verbose_name = "Location"
        verbose_name_plural = "Locations"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Directory(models.Model):
    """Directory paths and metadata.

    Stores information about directories containing photos, including
    their type, last modification time, and mirror status.
    """

    path = models.CharField(
        max_length=2048, unique=True, help_text="Full path to the directory"
    )
    last_modified = models.DateTimeField(
        help_text="Last modification time of the directory"
    )
    mirror = models.IntegerField(help_text="Mirror status indicator")
    kind = models.ForeignKey(
        DirKind,
        on_delete=models.CASCADE,
        related_name="directories",
        help_text="Directory kind/category",
    )

    class Meta:
        db_table = "Directories"
        verbose_name = "Directory"
        verbose_name_plural = "Directories"
        ordering = ["path"]
        indexes = [
            models.Index(fields=["kind"]),
            models.Index(fields=["last_modified"]),
        ]

    def __str__(self):
        return self.path


class Hash(models.Model):
    """File paths and their MD5 hashes.

    Stores photo file paths along with their MD5 hash values for
    duplicate detection and file identification.
    """

    path = models.CharField(
        max_length=2048, unique=True, help_text="Full path to the photo file"
    )
    hash = models.CharField(
        max_length=32,
        help_text="MD5 hash of the file (32 characters)",
        validators=[
            RegexValidator(
                regex=r"^[a-f0-9]{32}$",
                message="Hash must be a 32-character hexadecimal string",
            )
        ],
    )

    class Meta:
        db_table = "Hash"
        verbose_name = "Photo Hash"
        verbose_name_plural = "Photo Hashes"
        ordering = ["path"]
        indexes = [
            models.Index(fields=["hash"]),
        ]

    def __str__(self):
        return f"{self.path} ({self.hash[:8]}...)"


class TimeLoc(models.Model):
    """Timestamp and location data.

    Associates directories with timestamps and locations for
    temporal and geographic organization of photos.
    """

    path = models.ForeignKey(
        Directory,
        on_delete=models.CASCADE,
        related_name="time_locs",
        help_text="Directory path",
    )
    timestamp = models.DateTimeField(
        help_text="Timestamp associated with the directory"
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.CASCADE,
        related_name="time_locs",
        help_text="Location associated with the directory",
    )

    class Meta:
        db_table = "TimeLoc"
        verbose_name = "Time Location"
        verbose_name_plural = "Time Locations"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["timestamp"]),
            models.Index(fields=["location"]),
        ]
        unique_together = [["path", "timestamp", "location"]]

    def __str__(self):
        return f"{self.path.path} @ {self.timestamp} - {self.location.name}"
