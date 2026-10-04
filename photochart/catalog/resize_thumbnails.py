"""Bulk catalog operations on stored thumbnails."""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

from django.db.models import Q
from tqdm import tqdm

from photochart.media.resolution import parse_resolution
from photochart.media.size import parse_byte_size

try:
    from photograph.models import Photograph

    HAS_DJANGO_BACKEND = True
except (ImportError, ModuleNotFoundError, Exception):
    Photograph = None
    HAS_DJANGO_BACKEND = False

LOGGER = logging.getLogger(__name__)


def _thumbnail_byte_size(photograph: Photograph) -> Optional[int]:
    if not photograph.thumbnail:
        return None
    try:
        return photograph.thumbnail.size
    except Exception:
        pass
    try:
        return os.path.getsize(photograph.thumbnail.path)
    except OSError:
        return None


def resize_all_thumbnails(
    resolution: str,
    max_size: Optional[str] = None,
) -> dict[str, Any]:
    """Resize stored catalog thumbnails to fit within *resolution*.

    Args:
        resolution: Preset name or ``WIDTHxHEIGHT`` string.
        max_size: Optional minimum stored thumbnail size; smaller files are
            skipped (e.g. ``800K``, ``10M``).

    Returns:
        Result dict with ``success``, counts, and ``errors``.
    """
    if not HAS_DJANGO_BACKEND:
        raise ImportError(
            "Django backend models not available.\n "
            "Please, run using the Django shell:\n"
            "`python manage.py shell [-i ipython]`"
        )

    result: dict[str, Any] = {
        "success": True,
        "resized": 0,
        "skipped_too_small": 0,
        "skipped_no_thumbnail": 0,
        "failed": 0,
        "errors": [],
    }

    resolution_tuple = parse_resolution(resolution)
    if resolution_tuple is None:
        result["success"] = False
        result["errors"].append(
            f"Invalid resolution format: '{resolution}'. "
            "Use format 'WIDTHxHEIGHT' or a preset name (e.g. 'low', 'medium', 'high')"
        )
        return result

    min_bytes: Optional[int] = None
    if max_size is not None:
        try:
            min_bytes = parse_byte_size(max_size)
        except ValueError as err:
            result["success"] = False
            result["errors"].append(str(err))
            return result

    queryset = Photograph.objects.exclude(Q(thumbnail="") | Q(thumbnail__isnull=True))
    total = queryset.count()

    with tqdm(
        total=total,
        desc="Resizing thumbnails",
        unit="photo",
        unit_scale=False,
        dynamic_ncols=True,
    ) as pbar:
        for photograph in queryset.iterator():
            pbar.update(1)
            if not photograph.thumbnail:
                result["skipped_no_thumbnail"] += 1
                continue

            thumb_size = _thumbnail_byte_size(photograph)
            if thumb_size is None:
                result["failed"] += 1
                result["errors"].append(
                    f"Photograph {photograph.pk}: could not determine thumbnail size"
                )
                continue

            if min_bytes is not None and thumb_size < min_bytes:
                result["skipped_too_small"] += 1
                continue

            if photograph.resize_stored_thumbnail(resolution_tuple):
                result["resized"] += 1
            else:
                result["failed"] += 1
                result["errors"].append(
                    f"Photograph {photograph.pk}: resize_stored_thumbnail failed"
                )

    return result
