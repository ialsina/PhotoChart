"""Resolution utilities for image processing.

This module provides functions to parse and convert resolution strings,
including support for both explicit resolutions (e.g., "1920x1080") and
named presets (e.g., "low", "medium", "high").
"""

import re
from typing import Optional, Tuple

# Resolution presets mapping
RESOLUTION_PRESETS = {
    "low": (640, 480),
    "medium": (1920, 1080),
    "high": (3840, 2160),  # 4K
    "4k": (3840, 2160),
    "1080p": (1920, 1080),
    "720p": (1280, 720),
    "480p": (854, 480),
    "360p": (640, 360),
    "240p": (426, 240),
    "small": (640, 480),
    "large": (3840, 2160),
    "xsmall": (320, 240),
    "xlarge": (7680, 4320),  # 8K
    "8k": (7680, 4320),
}


def parse_resolution(resolution: Optional[str]) -> Optional[Tuple[int, int]]:
    """Parse a resolution string into width and height tuple.

    Supports both explicit formats (e.g., "1920x1080") and named presets
    (e.g., "low", "medium", "high").

    Args:
        resolution: Resolution string in format "WIDTHxHEIGHT" or a preset name

    Returns:
        Tuple of (width, height) in pixels, or None if parsing fails

    Examples:
        >>> parse_resolution("1920x1080")
        (1920, 1080)
        >>> parse_resolution("low")
        (640, 480)
        >>> parse_resolution("medium")
        (1920, 1080)
        >>> parse_resolution("high")
        (3840, 2160)
        >>> parse_resolution("invalid")
        None
    """
    if not resolution:
        return None

    resolution = resolution.strip().lower()

    # Check if it's a named preset
    if resolution in RESOLUTION_PRESETS:
        return RESOLUTION_PRESETS[resolution]

    # Try to parse as "WIDTHxHEIGHT" format
    match = re.match(r"^(\d+)\s*[xX]\s*(\d+)$", resolution)
    if match:
        width = int(match.group(1))
        height = int(match.group(2))
        if width > 0 and height > 0:
            return (width, height)

    return None


def format_resolution(resolution: Optional[Tuple[int, int]]) -> Optional[str]:
    """Format a resolution tuple as a string.

    Args:
        resolution: Tuple of (width, height) in pixels

    Returns:
        Formatted string like "1920x1080", or None if resolution is None

    Examples:
        >>> format_resolution((1920, 1080))
        '1920x1080'
        >>> format_resolution(None)
        None
    """
    if resolution is None:
        return None
    return f"{resolution[0]}x{resolution[1]}"


def get_resolution_presets() -> dict[str, Tuple[int, int]]:
    """Get all available resolution presets.

    Returns:
        Dictionary mapping preset names to (width, height) tuples
    """
    return RESOLUTION_PRESETS.copy()
