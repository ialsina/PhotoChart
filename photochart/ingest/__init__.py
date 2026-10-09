"""Catalog photo ingestion and host/Docker orchestration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .runner import (
    build_device_label,
    choose_and_run_ingest,
    resolve_mount_root,
    run_ingest_docker,
    run_ingest_local,
    validate_ingest_path,
)

if TYPE_CHECKING:
    from .photos import ingest_photos, is_image_file

__all__ = [
    "build_device_label",
    "choose_and_run_ingest",
    "ingest_photos",
    "is_image_file",
    "resolve_mount_root",
    "run_ingest_docker",
    "run_ingest_local",
    "validate_ingest_path",
]


def __getattr__(name: str):
    if name == "ingest_photos":
        from .photos import ingest_photos

        return ingest_photos
    if name == "is_image_file":
        from .photos import is_image_file

        return is_image_file
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
