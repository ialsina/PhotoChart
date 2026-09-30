"""Supported media file extensions (always lowercase, with leading dot)."""

from __future__ import annotations

from collections.abc import Iterable

RASTER_IMAGE_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".bmp",
        ".tiff",
        ".tif",
        ".webp",
    }
)

RAW_IMAGE_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".3fr",
        ".ari",
        ".arw",
        ".bay",
        ".cap",
        ".cr2",
        ".crw",
        ".dcs",
        ".dcr",
        ".dng",
        ".drf",
        ".eip",
        ".erf",
        ".fff",
        ".iiq",
        ".k25",
        ".kdc",
        ".mdc",
        ".mef",
        ".mos",
        ".mrw",
        ".nef",
        ".nrw",
        ".obm",
        ".orf",
        ".pef",
        ".pxn",
        ".r3d",
        ".raf",
        ".raw",
        ".rwl",
        ".rw2",
        ".rwz",
        ".sr2",
        ".srf",
        ".srw",
        ".x3f",
    }
)

OTHER_IMAGE_EXTENSIONS: frozenset[str] = frozenset({".heic", ".heif"})

VIDEO_EXTENSIONS: frozenset[str] = frozenset({".m4v", ".mov", ".mp4"})

IMAGE_EXTENSIONS: frozenset[str] = (
    RASTER_IMAGE_EXTENSIONS | RAW_IMAGE_EXTENSIONS | OTHER_IMAGE_EXTENSIONS
)

DEFAULT_ORGANIZER_MEDIA_EXTENSIONS: tuple[str, ...] = tuple(
    sorted(IMAGE_EXTENSIONS | VIDEO_EXTENSIONS)
)


def normalize_extension(extension: str) -> str:
    """Return a lowercase extension with a leading dot."""
    value = extension.strip().lower()
    if not value:
        raise ValueError("extension must be non-empty")
    if not value.startswith("."):
        value = f".{value}"
    return value


def normalize_extensions(extensions: Iterable[str]) -> tuple[str, ...]:
    """Normalize a sequence of extensions, preserving order and dropping duplicates."""
    seen: set[str] = set()
    normalized: list[str] = []
    for extension in extensions:
        item = normalize_extension(extension)
        if item not in seen:
            seen.add(item)
            normalized.append(item)
    return tuple(normalized)
