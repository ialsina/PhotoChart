"""EXIF metadata extraction utilities.

This module provides functions to extract specific EXIF tags from image files,
optimized to read the image file only once when extracting multiple tags.
Use ``full=True`` for comprehensive multi-IFD extraction (e.g. CLI ``pchart info -a``).
"""

from datetime import datetime
from enum import Enum, IntEnum
from fractions import Fraction
from typing import Dict, Any, Optional, List, Mapping
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


# Sub-IFD pointer tag IDs (IFD0) — values are expanded via get_ifd(), not serialized.
_SUB_IFD_POINTER_IDS = frozenset({0x8769, 0x8825, 0xA005, 0x010000})


def extract_exif(
    file_path: str,
    tags: Optional[List[ExifTagName]] = None,
    full: bool = False,
) -> Dict[str, Any]:
    """Extract EXIF metadata from an image file.

    Reads the image file only once.

    Limited mode (``full=False``, default): returns only requested logical tags:
    - ExifTagName.DATETIME: photograph datetime (``datetime`` object)
    - ExifTagName.MODEL: camera model (``str``)

    Full mode (``full=True``): returns human-readable EXIF tag names with
    JSON-friendly values from IFD0, the Exif sub-IFD, GPS, and ``img.info``.
    The ``tags`` argument is ignored when ``full=True``.

    Args:
        file_path: Path to the image file
        tags: List of ExifTagName enum values to extract. If None or empty,
            extracts all supported tags. Ignored when ``full=True``.
        full: When True, extract all available EXIF fields.

    Returns:
        Dictionary of extracted values. Keys depend on mode; missing tags are None
        in limited mode.
    """
    if full:
        try:
            from PIL import Image

            with Image.open(file_path) as img:
                return _extract_full_exif_from_image(img)
        except Exception:
            return {}

    if tags is None:
        tags = [ExifTagName.DATETIME, ExifTagName.MODEL]
    else:
        valid_tags = []
        for tag in tags:
            if isinstance(tag, ExifTagName):
                valid_tags.append(tag)
            elif isinstance(tag, str):
                try:
                    valid_tags.append(ExifTagName(tag.lower()))
                except ValueError:
                    continue
        tags = valid_tags

    tag_strings = [tag.value for tag in tags]
    result: Dict[str, Any] = {tag: None for tag in tag_strings}

    try:
        from PIL import Image
        from PIL.ExifTags import TAGS

        with Image.open(file_path) as img:
            exif_data = img.getexif()
            if not exif_data:
                return result

            if ExifTagName.DATETIME in tags:
                result[ExifTagName.DATETIME.value] = _extract_datetime_from_exif(
                    exif_data
                )

            if ExifTagName.MODEL in tags:
                result[ExifTagName.MODEL.value] = _extract_model_from_exif(
                    exif_data, TAGS
                )

    except Exception:
        pass

    return result


def _get_exif_tag(exif_data: Any, tag_id: int) -> Any:
    """Return a tag value from IFD0 or the Exif sub-IFD."""
    value = exif_data.get(tag_id)
    if value is not None:
        return value
    try:
        from PIL.ExifTags import IFD

        exif_ifd = exif_data.get_ifd(IFD.Exif)
        return exif_ifd.get(tag_id)
    except Exception:
        return None


def _serialize_exif_value(value: Any) -> Any:
    """Convert EXIF values to JSON-friendly Python types."""
    if value is None:
        return None
    if isinstance(value, bytes):
        try:
            decoded = value.decode("utf-8", errors="ignore").strip("\x00").strip()
            if decoded:
                return decoded
        except Exception:
            pass
        return f"<binary data: {len(value)} bytes>"
    if isinstance(value, (Fraction,)):
        return float(value)
    if hasattr(value, "numerator") and hasattr(value, "denominator"):
        try:
            return float(value)
        except (TypeError, ValueError, ZeroDivisionError):
            return str(value)
    if isinstance(value, tuple):
        return [_serialize_exif_value(item) for item in value]
    if isinstance(value, list):
        return [_serialize_exif_value(item) for item in value]
    if isinstance(value, dict):
        return {str(k): _serialize_exif_value(v) for k, v in value.items()}
    if isinstance(value, (int, float, str, bool)):
        return value
    return str(value)


def _merge_ifd_tags(
    target: Dict[str, Any],
    ifd_data: Mapping[int, Any],
    tags_dict: Dict[int, str],
    skip_tag_ids: frozenset[int] = frozenset(),
) -> None:
    for tag_id, value in ifd_data.items():
        if tag_id in skip_tag_ids:
            continue
        tag_name = tags_dict.get(tag_id, tag_id)
        if isinstance(tag_name, int):
            tag_name = str(tag_name)
        target[tag_name] = _serialize_exif_value(value)


def _extract_full_exif_from_image(img: Any) -> Dict[str, Any]:
    from PIL.ExifTags import TAGS, GPSTAGS, IFD

    result: Dict[str, Any] = {}
    exif_data = img.getexif()
    if exif_data:
        _merge_ifd_tags(
            result,
            exif_data,
            TAGS,
            skip_tag_ids=_SUB_IFD_POINTER_IDS,
        )
        try:
            exif_ifd = exif_data.get_ifd(IFD.Exif)
            _merge_ifd_tags(result, exif_ifd, TAGS)
        except Exception:
            pass
        try:
            gps_ifd = exif_data.get_ifd(IFD.GPSInfo)
            if gps_ifd:
                gps_data: Dict[str, Any] = {}
                _merge_ifd_tags(gps_data, gps_ifd, GPSTAGS)
                if gps_data:
                    result["GPSInfo"] = gps_data
        except Exception:
            pass
        try:
            interop_ifd = exif_data.get_ifd(IFD.Interop)
            if interop_ifd:
                interop_data: Dict[str, Any] = {}
                _merge_ifd_tags(interop_data, interop_ifd, TAGS)
                for key, value in interop_data.items():
                    prefixed = f"Interop:{key}"
                    if prefixed not in result:
                        result[prefixed] = value
        except Exception:
            pass

    if hasattr(img, "info"):
        for key, value in img.info.items():
            if key not in result:
                result[key] = _serialize_exif_value(value)

    return result


def _extract_datetime_from_exif(exif_data: Any) -> Optional[datetime]:
    """Extract datetime from EXIF data.

    Tries to extract the datetime from EXIF tags in order of preference:
    1. DateTimeOriginal (tag 36867) - when the photo was taken
    2. DateTimeDigitized (tag 36868) - when the photo was digitized
    3. DateTime (tag 306) - general datetime

    Checks IFD0 and the Exif sub-IFD.
    """
    datetime_str = _get_exif_tag(exif_data, ExifTag.DATETIME_ORIGINAL)
    if not datetime_str:
        datetime_str = _get_exif_tag(exif_data, ExifTag.DATETIME_DIGITIZED)
    if not datetime_str:
        datetime_str = _get_exif_tag(exif_data, ExifTag.DATETIME)

    if datetime_str:
        if isinstance(datetime_str, bytes):
            try:
                datetime_str = datetime_str.decode("utf-8", errors="ignore")
            except Exception:
                return None

        if not isinstance(datetime_str, str):
            datetime_str = str(datetime_str)

        datetime_str = datetime_str.strip()

        if not datetime_str:
            return None

        try:
            return datetime.strptime(datetime_str, "%Y:%m:%d %H:%M:%S")
        except (ValueError, TypeError):
            try:
                return datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError):
                return None

    return None


def _iter_exif_tag_items(exif_data: Any, tags_dict: Dict) -> List[tuple]:
    """Yield (tag_id, value) from IFD0 and the Exif sub-IFD."""
    items: List[tuple] = list(exif_data.items())
    try:
        from PIL.ExifTags import IFD

        exif_ifd = exif_data.get_ifd(IFD.Exif)
        items.extend(exif_ifd.items())
    except Exception:
        pass
    return items


def _extract_model_from_exif(exif_data: Any, tags_dict: Dict) -> Optional[str]:
    """Extract camera model from EXIF data (IFD0 and Exif sub-IFD)."""
    model_value = _get_exif_tag(exif_data, ExifTag.MODEL)
    if model_value:
        model_str = str(model_value).strip().replace("\x00", "")
        if model_str:
            return model_str

    for tag_id, value in _iter_exif_tag_items(exif_data, tags_dict):
        tag_name = tags_dict.get(tag_id, tag_id)
        if tag_name == "Model" and value:
            model_str = str(value).strip().replace("\x00", "")
            if model_str:
                return model_str

    for tag_id, value in _iter_exif_tag_items(exif_data, tags_dict):
        tag_name = tags_dict.get(tag_id, tag_id)
        if tag_name in ("CameraModelName", "Camera Model") and value:
            model_str = str(value).strip().replace("\x00", "")
            if model_str:
                return model_str

    return None


def extract_exif_datetime(file_path: str) -> Optional[datetime]:
    """Extract datetime from EXIF metadata of an image file.

    Convenience function that extracts only the datetime tag.
    """
    result = extract_exif(file_path, [ExifTagName.DATETIME])
    return result.get(ExifTagName.DATETIME.value)


def extract_exif_model(file_path: str) -> Optional[str]:
    """Extract camera model from EXIF metadata of an image file.

    Convenience function that extracts only the model tag.
    """
    result = extract_exif(file_path, [ExifTagName.MODEL])
    return result.get(ExifTagName.MODEL.value)
