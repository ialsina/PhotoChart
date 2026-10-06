"""Metadata extraction utilities for image files.

This module provides functions to extract comprehensive metadata from image files,
including EXIF data, RAW image metadata, and file information.
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional
from logging import Logger

from photochart.common.log import get_logger
from photochart.imaging.backends import get_backend

LOGGER = get_logger(__name__)


def extract_metadata(file_path: str, logger: Logger = LOGGER) -> Dict[str, Any]:
    """Extract all available metadata from an image file.

    This function extracts metadata from both standard image formats (JPEG, PNG, etc.)
    and RAW formats (NEF, CR2, etc.). It returns a comprehensive dictionary with
    all available metadata including EXIF data, file information, and RAW-specific data.

    Args:
        file_path: Path to the image file
        logger: Logger instance for error reporting

    Returns:
        Dictionary containing all available metadata, organized by category:
        - file: File system information (size, path, extension, etc.)
        - exif: EXIF metadata (if available)
        - raw: RAW-specific metadata (if applicable)
        - image: Image properties (dimensions, format, mode, etc.)

    Examples:
        >>> metadata = extract_metadata("photo.jpg")
        >>> print(metadata["exif"]["DateTimeOriginal"])
        '2023:12:25 14:30:00'
    """
    metadata: Dict[str, Any] = {
        "file": {},
        "exif": {},
        "raw": {},
        "image": {},
    }

    if not os.path.exists(file_path):
        logger.error("File does not exist: %s", file_path)
        return metadata

    # Extract file system metadata
    path = Path(file_path)
    stat = os.stat(file_path)
    metadata["file"] = {
        "path": str(path.absolute()),
        "name": path.name,
        "extension": path.suffix.lower(),
        "size": stat.st_size,
        "size_mb": round(stat.st_size / (1024 * 1024), 2),
        "created": stat.st_ctime,
        "modified": stat.st_mtime,
    }

    # Try to extract metadata using backend first (for RAW files)
    backend = get_backend(file_path)
    if backend:
        raw_metadata = _extract_raw_metadata(file_path, logger)
        if raw_metadata:
            metadata["raw"] = raw_metadata

    # Extract standard image metadata using PIL
    pil_metadata = _extract_pil_metadata(file_path, logger)
    if pil_metadata:
        metadata["image"].update(pil_metadata.get("image", {}))
        metadata["exif"].update(pil_metadata.get("exif", {}))

    return metadata


def _raw_metadata_from_rawpy_object(raw: Any) -> Dict[str, Any]:
    """Build a metadata dict from an opened ``rawpy.RawPy`` instance.

    Only uses attributes documented in the rawpy API; skips missing fields so
    newer/older rawpy builds do not break extraction.
    """
    raw_metadata: Dict[str, Any] = {}

    if hasattr(raw, "raw_type"):
        raw_metadata["raw_type"] = str(raw.raw_type)
    if hasattr(raw, "num_colors"):
        raw_metadata["num_colors"] = raw.num_colors

    if hasattr(raw, "sizes"):
        sizes = raw.sizes
        raw_metadata["sizes"] = {
            "raw_size": {
                "width": sizes.raw_width,
                "height": sizes.raw_height,
            },
            "top_margin": sizes.top_margin,
            "left_margin": sizes.left_margin,
            "iwidth": sizes.iwidth,
            "iheight": sizes.iheight,
            "pixel_aspect": sizes.pixel_aspect,
        }

    if hasattr(raw, "color_desc") and raw.color_desc:
        color_desc = raw.color_desc
        if isinstance(color_desc, bytes):
            raw_metadata["color_desc"] = color_desc.decode("utf-8", errors="ignore")
        else:
            raw_metadata["color_desc"] = str(color_desc)

    if hasattr(raw, "camera_whitebalance"):
        raw_metadata["camera_whitebalance"] = list(raw.camera_whitebalance)

    if hasattr(raw, "color_matrix"):
        matrix = raw.color_matrix
        if hasattr(matrix, "tolist"):
            raw_metadata["color_matrix"] = matrix.tolist()
        else:
            raw_metadata["color_matrix"] = matrix

    if hasattr(raw, "white_level"):
        raw_metadata["white_level"] = raw.white_level

    if hasattr(raw, "extract_thumb"):
        try:
            thumb = raw.extract_thumb()
            raw_metadata["thumbnail"] = {
                "format": str(thumb.format),
                "width": thumb.width,
                "height": thumb.height,
                "size": len(thumb.data) if thumb.data else 0,
            }
        except Exception:
            pass

    return raw_metadata


def _extract_raw_metadata(file_path: str, logger: Logger = LOGGER) -> Dict[str, Any]:
    """Extract metadata from RAW image files using rawpy.

    Args:
        file_path: Path to the RAW image file
        logger: Logger instance for error reporting

    Returns:
        Dictionary containing RAW-specific metadata, or empty dict if extraction fails
    """
    try:
        import rawpy

        with rawpy.imread(file_path) as raw:
            return _raw_metadata_from_rawpy_object(raw)

    except ImportError:
        logger.debug("rawpy not available for RAW metadata extraction")
    except Exception as exc:
        logger.warning("Failed to extract RAW metadata from %s: %s", file_path, exc)

    return {}


def _extract_pil_metadata(file_path: str, logger: Logger = LOGGER) -> Dict[str, Any]:
    """Extract metadata from standard image files using PIL/Pillow.

    Args:
        file_path: Path to the image file
        logger: Logger instance for error reporting

    Returns:
        Dictionary containing image and EXIF metadata, or empty dict if extraction fails
    """
    metadata: Dict[str, Any] = {"image": {}, "exif": {}}

    try:
        from PIL import Image
        from PIL.ExifTags import TAGS, GPSTAGS

        with Image.open(file_path) as img:
            # Extract basic image properties
            metadata["image"] = {
                "format": img.format,
                "mode": img.mode,
                "size": {"width": img.width, "height": img.height},
                "has_transparency": img.mode in ("RGBA", "LA", "P"),
            }

            # Extract EXIF data
            exif_data = img.getexif()
            if exif_data:
                # Standard EXIF tags
                for tag_id, value in exif_data.items():
                    tag_name = TAGS.get(tag_id, tag_id)
                    # Convert bytes to string if necessary
                    if isinstance(value, bytes):
                        try:
                            value = value.decode("utf-8", errors="ignore")
                        except Exception:
                            value = f"<binary data: {len(value)} bytes>"
                    metadata["exif"][tag_name] = value

                # Extract GPS data if available
                if 34853 in exif_data:  # GPSInfo tag
                    gps_info = exif_data[34853]
                    gps_data = {}
                    for tag_id, value in gps_info.items():
                        tag_name = GPSTAGS.get(tag_id, tag_id)
                        gps_data[tag_name] = value
                    metadata["exif"]["GPSInfo"] = gps_data

            # Try to get additional metadata
            if hasattr(img, "info"):
                for key, value in img.info.items():
                    if key not in metadata["exif"]:
                        # Convert bytes to string if necessary
                        if isinstance(value, bytes):
                            try:
                                value = value.decode("utf-8", errors="ignore")
                            except Exception:
                                value = f"<binary data: {len(value)} bytes>"
                        metadata["exif"][key] = value

    except Exception as exc:
        logger.warning("Failed to extract PIL metadata from %s: %s", file_path, exc)

    return metadata
