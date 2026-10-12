"""Configure Pillow decompression-bomb limits from environment or Django settings."""

from __future__ import annotations

from typing import Optional, Tuple

from photochart.common.log import get_logger

LOGGER = get_logger(__name__)

_CONFIGURED = False


def parse_max_image_pixels(raw: Optional[str]) -> Optional[int]:
    """Parse MAX_IMAGE_PIXELS; None means keep Pillow's built-in default."""
    if raw is None:
        return None
    stripped = raw.strip()
    if not stripped or stripped.lower() == "null":
        return None
    try:
        value = int(stripped)
    except ValueError as exc:
        raise ValueError(
            f"MAX_IMAGE_PIXELS must be a positive integer or null, got: {raw!r}"
        ) from exc
    if value <= 0:
        raise ValueError(f"MAX_IMAGE_PIXELS must be positive, got: {value}")
    return value


def resolve_pillow_pixel_limits() -> Tuple[bool, Optional[int]]:
    """Return (enable_check, max_pixels_override). max_pixels None = Pillow default."""
    enable = True
    max_raw = ""

    try:
        from django.conf import settings

        if settings.configured:
            enable = bool(getattr(settings, "ENABLE_MAX_IMAGE_PIXELS", True))
            max_raw = str(getattr(settings, "MAX_IMAGE_PIXELS", "") or "")
            return enable, parse_max_image_pixels(max_raw if max_raw else None)
    except Exception:
        pass

    try:
        from decouple import config

        enable = config("ENABLE_MAX_IMAGE_PIXELS", default=True, cast=bool)
        max_raw = config("MAX_IMAGE_PIXELS", default="")
    except Exception:
        pass

    return enable, parse_max_image_pixels(max_raw if max_raw else None)


def configure_pillow_once() -> None:
    """Apply ENABLE_MAX_IMAGE_PIXELS / MAX_IMAGE_PIXELS to PIL.Image.MAX_IMAGE_PIXELS."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    from PIL import Image

    enable, max_pixels = resolve_pillow_pixel_limits()

    if not enable:
        Image.MAX_IMAGE_PIXELS = None
        LOGGER.warning(
            "Pillow decompression-bomb protection is disabled "
            "(ENABLE_MAX_IMAGE_PIXELS=false)."
        )
    elif max_pixels is not None:
        Image.MAX_IMAGE_PIXELS = max_pixels
        LOGGER.info(
            "Pillow MAX_IMAGE_PIXELS set to %s (hard error above %s pixels).",
            max_pixels,
            2 * max_pixels,
        )

    _CONFIGURED = True


def reset_pillow_configure_state_for_tests() -> None:
    """Allow configure_pillow_once to run again (tests only)."""
    global _CONFIGURED
    _CONFIGURED = False
