"""Photograph models for managing photo files and their paths.

This module provides Django models for storing photograph metadata,
including file hashes and image references, as well as tracking
photo paths across different devices.
"""

import os
from django.db import models
from django.core.files import File
from django.core.validators import RegexValidator


class Photograph(models.Model):
    """Photograph model storing photo metadata.

    Represents a photograph with optional hash and image file.
    The hash can be computed using the calculate_hash function from
    photofinder.protocols.
    """

    hash = models.CharField(
        max_length=32,
        null=True,
        blank=True,
        help_text="MD5 hash of the photo file (32 characters)",
        validators=[
            RegexValidator(
                regex=r"^[a-f0-9]{32}$",
                message="Hash must be a 32-character hexadecimal string",
            )
        ],
    )
    image = models.ImageField(
        upload_to="photographs/",
        null=True,
        blank=True,
        help_text="Image file for the photograph",
    )
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="Timestamp when the photograph record was created"
    )
    updated_at = models.DateTimeField(
        auto_now=True, help_text="Timestamp when the photograph record was last updated"
    )

    class Meta:
        verbose_name = "Photograph"
        verbose_name_plural = "Photographs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["hash"]),
        ]

    def __str__(self):
        if self.hash:
            return f"Photograph ({self.hash[:8]}...)"
        elif self.image:
            return f"Photograph ({self.image.name})"
        else:
            return f"Photograph (id: {self.id})"

    def compute_hash_from_image(self):
        """Compute and set the hash from the image file if available.

        Uses the calculate_hash function from photofinder.protocols.

        Returns:
            The computed hash string, or None if computation fails
        """
        if self.image and self.image.path:
            from photofinder.protocols import calculate_hash

            hash_value = calculate_hash(self.image.path)
            if hash_value:
                self.hash = hash_value
                self.save(update_fields=["hash"])
            return hash_value
        return None

    def compute_hash_from_file(self, file_path):
        """Compute and set the hash from an external file path.

        Uses the calculate_hash function from photofinder.protocols.

        Args:
            file_path: Path to the file to compute hash from

        Returns:
            The computed hash string, or None if computation fails
        """
        if not file_path or not os.path.exists(file_path):
            return None

        from photofinder.protocols import calculate_hash

        hash_value = calculate_hash(file_path)
        if hash_value:
            self.hash = hash_value
            self.save(update_fields=["hash"])
        return hash_value

    def get_image_from_file(self, file_path):
        """Load an image from an external file path into the image field.

        Opens the file at the given path and saves it to the model's image field.
        The file will be saved with its original filename in the upload directory.

        Args:
            file_path: Path to the image file to load

        Returns:
            True if the image was successfully loaded, False otherwise
        """
        if not file_path or not os.path.exists(file_path):
            return False

        try:
            # Get the filename from the path
            filename = os.path.basename(file_path)

            # Open the file and save it to the image field
            with open(file_path, "rb") as f:
                self.image.save(filename, File(f), save=True)
            return True
        except Exception as e:
            # Log error if needed (you might want to add logging here)
            return False


class PhotoPath(models.Model):
    """Photo path model tracking file locations across devices.

    Represents a file path where a photograph exists, associated with
    a device and optionally linked to a Photograph instance.
    """

    path = models.CharField(max_length=2048, help_text="Full path to the photo file")
    device = models.CharField(
        max_length=255, help_text="Device identifier where the photo is located"
    )
    photograph = models.ForeignKey(
        Photograph,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="paths",
        help_text="Associated photograph (optional)",
    )
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="Timestamp when the path record was created"
    )
    updated_at = models.DateTimeField(
        auto_now=True, help_text="Timestamp when the path record was last updated"
    )

    class Meta:
        verbose_name = "Photo Path"
        verbose_name_plural = "Photo Paths"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["path"]),
            models.Index(fields=["device"]),
            models.Index(fields=["photograph"]),
        ]
        unique_together = [["path", "device"]]

    def __str__(self):
        return f"{self.path} on {self.device}"

    def save(self, *args, **kwargs):
        """Override save to automatically create or link Photograph.

        When a PhotoPath is saved and no photograph is linked, this will:
        1. Check if the file at the path exists
        2. Compute the hash from the file
        3. Find or create a Photograph with that hash
        4. Link this PhotoPath to the Photograph

        If a Photograph with the same hash already exists, it will be linked.
        Otherwise, a new Photograph will be created with the computed hash.
        """
        # Only process if photograph is not already set and file exists
        if not self.photograph and self.path and os.path.exists(self.path):
            from photofinder.protocols import calculate_hash

            # Compute hash from the file
            hash_value = calculate_hash(self.path)

            if hash_value:
                # Find or create a Photograph with this hash
                photograph, created = Photograph.objects.get_or_create(
                    hash=hash_value, defaults={}
                )

                # Link this PhotoPath to the Photograph
                self.photograph = photograph

        # Call the parent save method
        super().save(*args, **kwargs)
