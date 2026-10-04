"""Media type constants and resolution parsing."""

from .extensions import (
    DEFAULT_ORGANIZER_MEDIA_EXTENSIONS,
    IMAGE_EXTENSIONS,
    OTHER_IMAGE_EXTENSIONS,
    RASTER_IMAGE_EXTENSIONS,
    RAW_IMAGE_EXTENSIONS,
    VIDEO_EXTENSIONS,
    normalize_extension,
    normalize_extensions,
)
from .resolution import (
    RESOLUTION_PRESETS,
    format_resolution,
    get_resolution_presets,
    parse_resolution,
)

__all__ = [
    "DEFAULT_ORGANIZER_MEDIA_EXTENSIONS",
    "IMAGE_EXTENSIONS",
    "OTHER_IMAGE_EXTENSIONS",
    "RASTER_IMAGE_EXTENSIONS",
    "RAW_IMAGE_EXTENSIONS",
    "RESOLUTION_PRESETS",
    "VIDEO_EXTENSIONS",
    "format_resolution",
    "get_resolution_presets",
    "normalize_extension",
    "normalize_extensions",
    "parse_resolution",
]
