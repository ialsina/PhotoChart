"""Catalog photo ingestion and host/Docker orchestration."""

from .photos import ingest_photos, is_image_file
from .runner import (
    build_device_label,
    choose_and_run_ingest,
    resolve_mount_root,
    run_ingest_docker,
    run_ingest_local,
    validate_ingest_path,
)

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
