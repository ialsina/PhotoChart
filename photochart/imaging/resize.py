"""Shared PIL resize helpers used by catalog thumbnails and ingest."""

from __future__ import annotations

import io
from typing import Tuple

from PIL import Image


def fit_within_resolution(
    image: Image.Image, resolution: Tuple[int, int]
) -> Image.Image:
    """Resize *image* to fit within *resolution* while preserving aspect ratio."""
    target_width, target_height = resolution
    original_width, original_height = image.size
    aspect_ratio = original_width / original_height
    target_aspect = target_width / target_height

    if aspect_ratio > target_aspect:
        new_width = target_width
        new_height = int(target_width / aspect_ratio)
    else:
        new_height = target_height
        new_width = int(target_height * aspect_ratio)

    return image.resize((new_width, new_height), Image.Resampling.LANCZOS)


def image_to_jpeg_buffer(image: Image.Image, *, quality: int = 95) -> io.BytesIO:
    """Convert a PIL image to a JPEG byte buffer."""
    if image.mode in ("RGBA", "LA", "P"):
        rgb_image = Image.new("RGB", image.size, (255, 255, 255))
        if image.mode == "P":
            image = image.convert("RGBA")
        rgb_image.paste(image, mask=image.split()[-1] if image.mode == "RGBA" else None)
        image = rgb_image
    elif image.mode not in ("RGB", "L"):
        image = image.convert("RGB")

    output_buffer = io.BytesIO()
    image.save(output_buffer, format="JPEG", quality=quality)
    output_buffer.seek(0)
    return output_buffer
