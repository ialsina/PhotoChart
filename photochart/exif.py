"""EXIF metadata extraction utilities.

This module provides functions to extract specific EXIF tags from image files,
optimized to read the image file only once when extracting multiple tags.
"""

from datetime import datetime
from enum import Enum, IntEnum
from typing import Dict, Any, Optional, List
from pathlib import Path


class ExifTag(IntEnum):
    """EXIF tag number constants."""

    DATETIME_ORIGINAL = 36867
    DATETIME_DIGITIZED = 36868
    DATETIME = 306
    MODEL = 272


class ExifTagName(str, Enum):
    """EXIF tag name constants for extraction requests."""

    DATETIME = "datetime"
    MODEL = "model"


def extract_exif(
    file_path: str, tags: Optional[List[ExifTagName]] = None
) -> Dict[str, Any]:
    """Extract specified EXIF tags from an image file.

    Reads the image file only once and extracts all requested tags.
    Supported tags:
    - ExifTagName.DATETIME: Extracts photograph datetime (returns datetime object)
    - ExifTagName.MODEL: Extracts camera model (returns string)

    Args:
        file_path: Path to the image file
        tags: List of ExifTagName enum values to extract. If None or empty,
            extracts all supported tags.

    Returns:
        Dictionary with extracted tag values. Keys are the string values of the
        requested tag names. Values are None if the tag was not found or extraction failed.

    Examples:
        >>> # Extract both datetime and model
        >>> result = extract_exif("photo.jpg", [ExifTagName.DATETIME, ExifTagName.MODEL])
        >>> print(result["datetime"])  # datetime object or None
        >>> print(result["model"])     # string or None

        >>> # Extract only datetime
        >>> result = extract_exif("photo.jpg", [ExifTagName.DATETIME])
        >>> print(result["datetime"])

        >>> # Extract all supported tags
        >>> result = extract_exif("photo.jpg")
    """
    if tags is None:
        tags = [ExifTagName.DATETIME, ExifTagName.MODEL]
    else:
        # Validate and normalize tag names
        valid_tags = []
        for tag in tags:
            if isinstance(tag, ExifTagName):
                valid_tags.append(tag)
            elif isinstance(tag, str):
                # Allow string values for backward compatibility
                try:
                    valid_tags.append(ExifTagName(tag.lower()))
                except ValueError:
                    # Skip invalid tag names
                    continue
        tags = valid_tags

    # Convert enum values to strings for dictionary keys
    tag_strings = [tag.value for tag in tags]
    result: Dict[str, Any] = {tag: None for tag in tag_strings}

    try:
        from PIL import Image
        from PIL.ExifTags import TAGS

        with Image.open(file_path) as img:
            # Get EXIF data
            exif_data = img.getexif()
            if not exif_data:
                return result

            # Extract datetime if requested
            if ExifTagName.DATETIME in tags:
                datetime_value = _extract_datetime_from_exif(exif_data)
                result[ExifTagName.DATETIME.value] = datetime_value

            # Extract model if requested
            if ExifTagName.MODEL in tags:
                model_value = _extract_model_from_exif(exif_data, TAGS)
                result[ExifTagName.MODEL.value] = model_value

    except Exception:
        # If extraction fails, return None for all requested tags
        # Don't raise exception - let caller handle missing data
        pass

    return result


def _extract_datetime_from_exif(exif_data: Any) -> Optional[datetime]:
    """Extract datetime from EXIF data.

    Tries to extract the datetime from EXIF tags in order of preference:
    1. DateTimeOriginal (tag 36867) - when the photo was taken
    2. DateTimeDigitized (tag 36868) - when the photo was digitized
    3. DateTime (tag 306) - general datetime

    Args:
        exif_data: EXIF data dictionary from PIL

    Returns:
        datetime object if found, None otherwise
    """
    datetime_str = None

    # Priority 1: DateTimeOriginal
    if ExifTag.DATETIME_ORIGINAL in exif_data:
        datetime_str = exif_data[ExifTag.DATETIME_ORIGINAL]
    # Priority 2: DateTimeDigitized
    elif ExifTag.DATETIME_DIGITIZED in exif_data:
        datetime_str = exif_data[ExifTag.DATETIME_DIGITIZED]
    # Priority 3: DateTime
    elif ExifTag.DATETIME in exif_data:
        datetime_str = exif_data[ExifTag.DATETIME]

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

    return None


def _extract_model_from_exif(exif_data: Any, tags_dict: Dict) -> Optional[str]:
    """Extract camera model from EXIF data.

    Tries to extract the camera model from EXIF tags:
    1. Model (tag 272) - camera model name
    2. CameraModelName - alternative tag name (some cameras use this)

    Args:
        exif_data: EXIF data dictionary from PIL
        tags_dict: PIL.ExifTags.TAGS dictionary for tag name lookup

    Returns:
        Camera model string if found, None otherwise
    """
    # Try to get Model tag directly
    if ExifTag.MODEL in exif_data:
        model_value = exif_data[ExifTag.MODEL]
        if model_value:
            # Clean up the model string (remove null bytes, strip whitespace)
            model_str = str(model_value).strip().replace("\x00", "")
            if model_str:
                return model_str

    # Try to find by tag name (for compatibility with different EXIF implementations)
    for tag_id, value in exif_data.items():
        tag_name = tags_dict.get(tag_id, tag_id)
        if tag_name == "Model" and value:
            model_str = str(value).strip().replace("\x00", "")
            if model_str:
                return model_str

    # Try alternative tag names
    for tag_id, value in exif_data.items():
        tag_name = tags_dict.get(tag_id, tag_id)
        if tag_name in ("CameraModelName", "Camera Model") and value:
            model_str = str(value).strip().replace("\x00", "")
            if model_str:
                return model_str

    return None


def extract_exif_datetime(file_path: str) -> Optional[datetime]:
    """Extract datetime from EXIF metadata of an image file.

    Convenience function that extracts only the datetime tag.

    Args:
        file_path: Path to the image file

    Returns:
        datetime object if found, None otherwise
    """
    result = extract_exif(file_path, [ExifTagName.DATETIME])
    return result.get(ExifTagName.DATETIME.value)


def extract_exif_model(file_path: str) -> Optional[str]:
    """Extract camera model from EXIF metadata of an image file.

    Convenience function that extracts only the model tag.

    Args:
        file_path: Path to the image file

    Returns:
        Camera model string if found, None otherwise
    """
    result = extract_exif(file_path, [ExifTagName.MODEL])
    return result.get(ExifTagName.MODEL.value)
