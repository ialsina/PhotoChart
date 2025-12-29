"""Photograph models for managing photo files and their paths.

This module provides Django models for storing photograph metadata,
including file hashes and image references, as well as tracking
photo paths across different devices.
"""

import os
from datetime import datetime
from django.db import models
from django.core.files import File
from django.core.validators import RegexValidator
from django.utils import timezone


class Photograph(models.Model):
    """Photograph model storing photo metadata.

    Represents a photograph with optional hash and image file.
    The hash can be computed using the calculate_hash function from
    photochart.protocols.
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
    time = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Photograph time extracted from EXIF metadata (when the photo was taken)",
    )
    has_errors = models.BooleanField(
        default=False,
        help_text="True if any error occurred during image creation or data reading",
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

    def _extract_exif_datetime(self, file_path):
        """Extract datetime from EXIF metadata of an image file.

        Tries to extract the datetime from EXIF tags in order of preference:
        1. DateTimeOriginal (tag 36867) - when the photo was taken
        2. DateTimeDigitized (tag 36868) - when the photo was digitized
        3. DateTime (tag 306) - general datetime

        Args:
            file_path: Path to the image file

        Returns:
            datetime object if found, None otherwise
        """
        try:
            from PIL import Image

            with Image.open(file_path) as img:
                # Get EXIF data
                exif_data = img.getexif()
                if not exif_data:
                    return None

                # Try to find datetime tags
                # EXIF tag numbers for datetime fields
                DATETIME_ORIGINAL = 36867
                DATETIME_DIGITIZED = 36868
                DATETIME = 306

                datetime_str = None

                # Priority 1: DateTimeOriginal
                if DATETIME_ORIGINAL in exif_data:
                    datetime_str = exif_data[DATETIME_ORIGINAL]
                # Priority 2: DateTimeDigitized
                elif DATETIME_DIGITIZED in exif_data:
                    datetime_str = exif_data[DATETIME_DIGITIZED]
                # Priority 3: DateTime
                elif DATETIME in exif_data:
                    datetime_str = exif_data[DATETIME]

                if datetime_str:
                    # Parse EXIF datetime format: "YYYY:MM:DD HH:MM:SS"
                    try:
                        return datetime.strptime(datetime_str, "%Y:%m:%d %H:%M:%S")
                    except (ValueError, TypeError):
                        # Try alternative formats if standard format fails
                        try:
                            return datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")
                        except (ValueError, TypeError):
                            return None

        except Exception:
            # If EXIF extraction fails for any reason, mark as error and return None
            self.has_errors = True
            self.save(update_fields=["has_errors"])
            return None

    def compute_hash_from_image(self):
        """Compute and set the hash from the image file if available.

        Uses the calculate_hash function from photochart.protocols.

        Returns:
            The computed hash string, or None if computation fails
        """
        try:
            if self.image and self.image.path:
                from photochart.protocols import calculate_hash

                hash_value = calculate_hash(self.image.path)
                if hash_value:
                    self.hash = hash_value
                    self.save(update_fields=["hash"])
                else:
                    # Hash computation failed (returned None)
                    self.has_errors = True
                    self.save(update_fields=["has_errors"])
                return hash_value
            # No image or path available - not an error, just can't compute
            return None
        except Exception:
            # Any exception during hash computation
            self.has_errors = True
            self.save(update_fields=["has_errors"])
            return None

    def compute_hash_from_file(self, file_path):
        """Compute and set the hash from an external file path.

        Uses the calculate_hash function from photochart.protocols.

        Args:
            file_path: Path to the file to compute hash from

        Returns:
            The computed hash string, or None if computation fails
        """
        try:
            if not file_path or not os.path.exists(file_path):
                self.has_errors = True
                self.save(update_fields=["has_errors"])
                return None

            from photochart.protocols import calculate_hash

            hash_value = calculate_hash(file_path)
            if hash_value:
                self.hash = hash_value
                self.save(update_fields=["hash"])
            else:
                # Hash computation failed
                self.has_errors = True
                self.save(update_fields=["has_errors"])
            return hash_value
        except Exception:
            # Any exception during hash computation
            self.has_errors = True
            self.save(update_fields=["has_errors"])
            return None

    def _generate_timestamp_filename(self, original_file_path, extension=None):
        """Generate a timestamp-based filename to avoid clashes.

        Uses the Photograph's created_at timestamp if available,
        otherwise uses the current time.

        Args:
            original_file_path: Original file path (used to determine extension if not provided)
            extension: File extension to use (e.g., ".jpg", ".png"). If None, auto-detects from original file.

        Returns:
            A filename string based on the creation timestamp
        """
        # Use created_at timestamp if available, otherwise use current time
        if self.created_at:
            timestamp = self.created_at
        else:
            timestamp = timezone.now()

        # Format timestamp as YYYYMMDD_HHMMSS_microseconds
        timestamp_str = timestamp.strftime("%Y%m%d_%H%M%S_%f")

        # If extension not provided, try to get it from original file
        if extension is None:
            _, original_ext = os.path.splitext(original_file_path)
            if original_ext and original_ext.lower() in [
                ".jpg",
                ".jpeg",
                ".png",
                ".gif",
                ".bmp",
                ".tiff",
                ".tif",
                ".webp",
            ]:
                extension = original_ext.lower()
                if extension == ".jpeg":
                    extension = ".jpg"
            else:
                extension = ".jpg"  # Default to .jpg if extension not recognized

        return f"{timestamp_str}{extension}"

    def get_image_from_file(self, file_path, resolution=None):
        """Load an image from an external file path into the image field.

        Opens the file at the given path and saves it to the model's image field.
        The file will be saved with a timestamp-based filename to avoid clashes.
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
                    from photochart.resolution import parse_resolution

                    resolution_tuple = parse_resolution(resolution)
                elif isinstance(resolution, tuple) and len(resolution) == 2:
                    resolution_tuple = resolution

            # Try to process through backend first (for special formats like NEF)
            from photochart.backends import process_image_file

            processed_image = process_image_file(
                file_path, output_format="JPEG", resolution=resolution_tuple
            )

            if processed_image:
                # Backend processed the image successfully
                # Generate timestamp-based filename (processed images are always JPEG)
                filename = self._generate_timestamp_filename(
                    file_path, extension=".jpg"
                )

                self.image.save(filename, File(processed_image), save=True)

                # Extract and set photograph time from EXIF if not already set
                if not self.time:
                    exif_time = self._extract_exif_datetime(file_path)
                    if exif_time:
                        self.time = (
                            timezone.make_aware(exif_time)
                            if timezone.is_naive(exif_time)
                            else exif_time
                        )
                        self.save(update_fields=["time"])

                return True

            # Fallback to direct file copy for standard formats
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

                # Use timestamp-based filename with .jpg extension for resized images
                filename = self._generate_timestamp_filename(
                    file_path, extension=".jpg"
                )

                self.image.save(filename, File(output_buffer), save=True)
            else:
                # No resolution specified, just copy the file directly
                # Generate timestamp-based filename preserving original extension
                filename = self._generate_timestamp_filename(file_path, extension=None)
                with open(file_path, "rb") as f:
                    self.image.save(filename, File(f), save=True)

            # Extract and set photograph time from EXIF if not already set
            if not self.time:
                exif_time = self._extract_exif_datetime(file_path)
                if exif_time:
                    self.time = (
                        timezone.make_aware(exif_time)
                        if timezone.is_naive(exif_time)
                        else exif_time
                    )
                    self.save(update_fields=["time"])

            return True
        except Exception as e:
            # Mark as error and return False
            self.has_errors = True
            self.save(update_fields=["has_errors"])
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
    file_created_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="File creation timestamp from the filesystem",
    )
    file_updated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="File modification timestamp from the filesystem",
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

        # Update file timestamps if path exists
        if self.path and os.path.exists(self.path):
            try:
                # Get file creation and modification times
                file_created = os.path.getctime(self.path)
                file_updated = os.path.getmtime(self.path)

                # Convert to datetime objects (fromtimestamp returns naive datetime in local timezone)
                file_created_dt = datetime.fromtimestamp(file_created)
                file_updated_dt = datetime.fromtimestamp(file_updated)

                # Make timezone-aware using Django's default timezone
                if timezone.is_naive(file_created_dt):
                    file_created_dt = timezone.make_aware(file_created_dt)
                if timezone.is_naive(file_updated_dt):
                    file_updated_dt = timezone.make_aware(file_updated_dt)

                # Always update file timestamps to reflect current file state
                self.file_created_at = file_created_dt
                self.file_updated_at = file_updated_dt
            except (OSError, ValueError):
                # If we can't get file timestamps, leave fields as None
                pass

        # Process photograph creation/linking if not already set and file exists
        if not self.photograph and self.path and os.path.exists(self.path):
            try:
                from photochart.protocols import calculate_hash

                # Compute hash from the file
                hash_value = calculate_hash(self.path)

                if hash_value:
                    # Find or create a Photograph with this hash
                    photograph, created = Photograph.objects.get_or_create(
                        hash=hash_value, defaults={}
                    )

                    # Link this PhotoPath to the Photograph
                    self.photograph = photograph
                else:
                    # Hash computation failed - create photograph without hash and mark error
                    photograph = Photograph.objects.create()
                    photograph.has_errors = True
                    photograph.save(update_fields=["has_errors"])
                    self.photograph = photograph
            except Exception:
                # Any error during hash computation or photograph creation
                photograph = Photograph.objects.create()
                photograph.has_errors = True
                photograph.save(update_fields=["has_errors"])
                self.photograph = photograph

        # Store image if requested (regardless of whether photograph was just created or already existed)
        if store_image and self.photograph and self.path and os.path.exists(self.path):
            try:
                if not self.photograph.image:
                    success = self.photograph.get_image_from_file(
                        self.path, resolution=resolution
                    )
                    if not success:
                        # Image loading failed - error already set in get_image_from_file
                        pass

                # Extract and set photograph time from EXIF if not already set
                if not self.photograph.time:
                    exif_time = self.photograph._extract_exif_datetime(self.path)
                    if exif_time:
                        self.photograph.time = (
                            timezone.make_aware(exif_time)
                            if timezone.is_naive(exif_time)
                            else exif_time
                        )
                        self.photograph.save(update_fields=["time"])
            except Exception:
                # Any error during image storage or EXIF extraction
                self.photograph.has_errors = True
                self.photograph.save(update_fields=["has_errors"])

        # Call the parent save method
        super().save(*args, **kwargs)
