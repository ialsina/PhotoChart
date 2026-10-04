"""Image conversion utilities for converting images to standard formats.

This module provides functions to convert image files to standard formats (like JPEG),
with support for special formats (NEF, RAW, etc.) and optional resizing.
"""

import os
import io
from pathlib import Path
from typing import Optional, Tuple
from logging import Logger

from .log import get_logger
from .protocols import cp, check_disk_space
from .backends import process_image_file
from .resolution import parse_resolution

LOGGER = get_logger(__name__)


def convert_image(
    src: str,
    dst: str,
    resolution: Optional[str] = None,
    output_format: str = "JPEG",
    logger: Logger = LOGGER,
) -> bool:
    """Convert an image file to a standard format with optional resizing.

    This function handles both special formats (like NEF, RAW) and standard formats.
    It uses the backend system for special formats and PIL for standard formats.
    The conversion preserves image quality and handles aspect ratio correctly.

    Args:
        src: Source file path
        dst: Destination file path
        resolution: Optional resolution string (e.g., "1920x1080" or "medium")
            or tuple (width, height). If None, original resolution is preserved.
        output_format: Output format (default: "JPEG")
        logger: Logger instance for operation tracking

    Returns:
        True if conversion was successful, False otherwise

    Examples:
        >>> convert_image("photo.nef", "photo.jpg")
        True
        >>> convert_image("photo.jpg", "photo_small.jpg", resolution="640x480")
        True
        >>> convert_image("photo.jpg", "photo_medium.jpg", resolution="medium")
        True
    """
    if not os.path.exists(src):
        logger.error("Source file does not exist: %s", src)
        return False

    # Ensure the destination directory exists
    dst_dir = os.path.dirname(dst)
    if dst_dir:
        os.makedirs(dst_dir, exist_ok=True)

    # Parse resolution if it's a string
    resolution_tuple = None
    if resolution:
        if isinstance(resolution, str):
            resolution_tuple = parse_resolution(resolution)
            if resolution_tuple is None:
                logger.warning(
                    "Invalid resolution format: %s. Ignoring resolution parameter.",
                    resolution,
                )
        elif isinstance(resolution, tuple) and len(resolution) == 2:
            resolution_tuple = resolution

    # Check disk space before conversion
    src_size = os.path.getsize(src)
    # Estimate destination size (may be larger if converting from RAW)
    estimated_dst_size = src_size * 2 if resolution_tuple else src_size
    if not check_disk_space(dst_dir or ".", estimated_dst_size, logger=logger):
        logger.error("Not enough disk space at destination: %s", dst_dir or ".")
        return False

    try:
        # Try to process through backend first (for special formats like NEF)
        processed_image = process_image_file(
            src, output_format=output_format, resolution=resolution_tuple, logger=logger
        )

        if processed_image:
            # Backend processed the image successfully
            # Write the processed image to destination
            with open(dst, "wb") as f:
                f.write(processed_image.read())
            logger.info("Successfully converted %s to %s", src, dst)
            return True

        # Fallback to PIL for standard formats
        from PIL import Image

        # Open the image
        image = Image.open(src)

        # Resize if resolution is specified
        if resolution_tuple:
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
            logger.debug(
                "Resized image to %dx%d (requested: %dx%d)",
                new_width,
                new_height,
                target_width,
                target_height,
            )

        # Convert image mode for JPEG output
        if output_format.upper() == "JPEG":
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

        # Save the image
        image.save(dst, format=output_format, quality=95)
        logger.info("Successfully converted %s to %s", src, dst)
        return True

    except Exception as exc:
        logger.error("Failed to convert %s to %s: %s", src, dst, exc)
        return False
