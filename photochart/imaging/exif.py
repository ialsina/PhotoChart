"""EXIF metadata extraction utilities.

This module provides functions to extract specific EXIF tags from image files,
optimized to read the image file only once when extracting multiple tags.
Use ``full=True`` for comprehensive multi-IFD extraction (e.g. CLI ``pchart info -a``).
"""

import io
from contextlib import contextmanager
from datetime import datetime
from enum import Enum, IntEnum
from fractions import Fraction
from pathlib import Path
from typing import Any, Dict, Iterator, List, Mapping, Optional

from photochart.media.extensions import RAW_IMAGE_EXTENSIONS


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

# Typical shooting EXIF keys shown by ``pchart info`` without ``--all``.
_INFO_SUMMARY_EXIF_KEYS = frozenset(
    {
        "Make",
        "Model",
        "ExposureTime",
        "FNumber",
        "PhotographicSensitivity",
        "ISOSpeedRatings",
        "FocalLength",
        "FocalLengthIn35mmFilm",
        "LensModel",
        "LensMake",
        "LensSpecification",
        "ExposureProgram",
        "MeteringMode",
        "Flash",
        "WhiteBalance",
        "ShutterSpeedValue",
        "ApertureValue",
    }
)


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
            with _exif_image(file_path) as img:
                if img is None:
                    return {}
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
        from PIL.ExifTags import TAGS

        with _exif_image(file_path) as img:
            if img is None:
                return result
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


def extract_exif_for_info(file_path: str, all_exif: bool = False) -> Dict[str, Any]:
    """EXIF payload for ``pchart info``.

    Without ``all_exif``, returns parsed ``datetime`` / ``model`` plus a curated
    set of common shooting tags (exposure, aperture, ISO, lens, etc.). With
    ``all_exif``, returns the complete EXIF dump (same as ``extract_exif(...,
    full=True)``).
    """
    if all_exif:
        return extract_exif(file_path, full=True)

    limited_defaults = {
        ExifTagName.DATETIME.value: None,
        ExifTagName.MODEL.value: None,
    }
    try:
        from PIL.ExifTags import TAGS

        with _exif_image(file_path) as img:
            if img is None:
                return limited_defaults
            exif_data = img.getexif()
            limited = {
                ExifTagName.DATETIME.value: (
                    _extract_datetime_from_exif(exif_data) if exif_data else None
                ),
                ExifTagName.MODEL.value: (
                    _extract_model_from_exif(exif_data, TAGS) if exif_data else None
                ),
            }
            full_tags = _extract_full_exif_from_image(img)
            summary = {
                key: value
                for key, value in full_tags.items()
                if key in _INFO_SUMMARY_EXIF_KEYS
            }
            return {**summary, **limited}
    except Exception:
        return limited_defaults


@contextmanager
def _exif_image(file_path: str) -> Iterator[Any]:
    """Open an image suitable for EXIF reads (file or RAW embedded JPEG)."""
    from PIL import Image

    img: Any = None
    embedded: Any = None
    try:
        try:
            img = Image.open(file_path)
            img.load()
            if img.getexif():
                yield img
                return
            img.close()
            img = None
        except Exception:
            if img is not None:
                try:
                    img.close()
                except Exception:
                    pass
            img = None

        embedded = _open_raw_embedded_jpeg_image(file_path)
        yield embedded
    finally:
        if img is not None:
            try:
                img.close()
            except Exception:
                pass
        if embedded is not None:
            try:
                embedded.close()
            except Exception:
                pass


def _open_raw_embedded_jpeg_image(file_path: str) -> Any:
    """Return a PIL image from a RAW file's embedded JPEG preview, if any."""
    if Path(file_path).suffix.lower() not in RAW_IMAGE_EXTENSIONS:
        return None
    try:
        import rawpy
        from PIL import Image

        with rawpy.imread(file_path) as raw:
            thumb = raw.extract_thumb()
        if thumb.format != rawpy.ThumbFormat.JPEG or not thumb.data:
            return None
        return Image.open(io.BytesIO(thumb.data))
    except Exception:
        return None


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
