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

    def get_image_from_file(self, file_path, resolution=None):
        """Load an image from an external file path into the image field.

        Opens the file at the given path and saves it to the model's image field.
        The file will be saved with its original filename in the upload directory.
        If the file requires special processing (e.g., NEF files), it will be
        processed through the appropriate backend.

        Args:
            file_path: Path to the image file to load
            resolution: Optional target resolution as (width, height) tuple or
                resolution string (e.g., "1920x1080" or "low", "medium", "high")

        Returns:
            True if the image was successfully loaded, False otherwise
        """
        if not file_path or not os.path.exists(file_path):
            return False

        try:
            # Parse resolution if it's a string
            resolution_tuple = None
            if resolution:
                if isinstance(resolution, str):
                    from photofinder.resolution import parse_resolution

                    resolution_tuple = parse_resolution(resolution)
                elif isinstance(resolution, tuple) and len(resolution) == 2:
                    resolution_tuple = resolution

            # Try to process through backend first (for special formats like NEF)
            from photofinder.backends import process_image_file

            processed_image = process_image_file(
                file_path, output_format="JPEG", resolution=resolution_tuple
            )

            if processed_image:
                # Backend processed the image successfully
                # Get the filename and change extension to .jpg if needed
                filename = os.path.basename(file_path)
                base_name, ext = os.path.splitext(filename)
                if ext.lower() in [".nef", ".raw", ".cr2", ".arw"]:
                    filename = f"{base_name}.jpg"

                self.image.save(filename, File(processed_image), save=True)
                return True

            # Fallback to direct file copy for standard formats
            # Get the filename from the path
            filename = os.path.basename(file_path)

            # If resolution is specified, we need to process even standard formats
            if resolution_tuple:
                from PIL import Image

                # Open and resize the image
                image = Image.open(file_path)
                target_width, target_height = resolution_tuple

                # Maintain aspect ratio
                original_width, original_height = image.size
                aspect_ratio = original_width / original_height
                target_aspect = target_width / target_height

                if aspect_ratio > target_aspect:
                    # Image is wider - fit to width
                    new_width = target_width
                    new_height = int(target_width / aspect_ratio)
                else:
                    # Image is taller - fit to height
                    new_height = target_height
                    new_width = int(target_height * aspect_ratio)

                image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

                # Save to BytesIO
                import io

                output_buffer = io.BytesIO()
                if image.mode in ("RGBA", "LA", "P"):
                    # Convert to RGB for JPEG
                    rgb_image = Image.new("RGB", image.size, (255, 255, 255))
                    if image.mode == "P":
                        image = image.convert("RGBA")
                    rgb_image.paste(
                        image, mask=image.split()[-1] if image.mode == "RGBA" else None
                    )
                    image = rgb_image
                elif image.mode not in ("RGB", "L"):
                    image = image.convert("RGB")

                image.save(output_buffer, format="JPEG", quality=95)
                output_buffer.seek(0)

                # Update filename extension if needed
                base_name, ext = os.path.splitext(filename)
                if ext.lower() not in [".jpg", ".jpeg"]:
                    filename = f"{base_name}.jpg"

                self.image.save(filename, File(output_buffer), save=True)
            else:
                # No resolution specified, just copy the file directly
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
        4. Optionally store the image file if store_image is True
        5. Link this PhotoPath to the Photograph

        If a Photograph with the same hash already exists, it will be linked.
        Otherwise, a new Photograph will be created with the computed hash.

        Keyword Args:
            store_image: If True, store the image file in the Photograph's image field
            resolution: Optional resolution for image storage (only used if store_image=True)
        """
        # Extract custom kwargs
        store_image = kwargs.pop("store_image", False)
        resolution = kwargs.pop("resolution", None)

        # Process photograph creation/linking if not already set and file exists
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

        # Store image if requested (regardless of whether photograph was just created or already existed)
        if store_image and self.photograph and self.path and os.path.exists(self.path):
            if not self.photograph.image:
                self.photograph.get_image_from_file(self.path, resolution=resolution)

        # Call the parent save method
        super().save(*args, **kwargs)
