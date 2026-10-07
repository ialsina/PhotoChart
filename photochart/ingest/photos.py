"""Photo ingestion functionality.

This module provides functions for ingesting photos from directories,
calculating checksums, and storing them in the database.
"""

import os
import socket
import logging
import traceback
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

from django.conf import settings
from django.db import transaction
from tqdm import tqdm

from photochart.fs.device import (
    get_device_name,
    get_mount_point,
    load_mount_table,
    mount_point_for_path,
)
from photochart.fs.protocols import calculate_checksum as calculate_file_checksum
from photochart.media.extensions import IMAGE_EXTENSIONS, RAW_IMAGE_EXTENSIONS
from photochart.media.resolution import parse_resolution

try:
    from photograph.models import PhotoPath, Photograph

    HAS_DJANGO_BACKEND = True
except (ImportError, ModuleNotFoundError, Exception):
    PhotoPath = None
    Photograph = None
    HAS_DJANGO_BACKEND = False


def _setup_logger(log_path: Optional[str] = None) -> Optional[logging.Logger]:
    """Set up a logger for ingestion operations.

    Args:
        log_path: Path to log file. If None, no logger is created.

    Returns:
        Logger instance if log_path is provided, None otherwise.
    """
    if not log_path:
        return None

    # Create logger
    logger = logging.getLogger("photochart.ingest")
    logger.setLevel(logging.DEBUG)

    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()

    # Create file handler
    try:
        log_file = Path(log_path)
        # Create parent directories if they don't exist
        log_file.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)

        # Create formatter with detailed information including file and line number
        formatter = logging.Formatter(
            fmt="%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(funcName)s() - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        logger.propagate = False  # Don't propagate to root logger

        return logger
    except Exception as e:
        # If we can't create the logger, return None and continue without logging
        # This prevents logging setup from breaking the ingestion process
        return None


def _resolved_media_root() -> Optional[Path]:
    """Return resolved MEDIA_ROOT, or None if unavailable."""
    try:
        return Path(settings.MEDIA_ROOT).resolve()
    except Exception:
        return None


def is_path_in_media_root(file_path: Path, media_root: Optional[Path] = None) -> bool:
    """Check if a file path is within the Django MEDIA_ROOT directory.

    This prevents ingesting files that are stored in the media directory,
    which would create a loop where:
    - A photo is ingested and its thumbnail is saved to MEDIA_ROOT
    - That thumbnail file gets ingested as a new Photograph
    - Which creates another thumbnail, etc.

    Args:
        file_path: Path to check

    Returns:
        True if the path is within MEDIA_ROOT, False otherwise
    """
    try:
        if media_root is None:
            media_root = _resolved_media_root()
        if media_root is None:
            return True
        file_path_resolved = file_path.resolve()
        # Check if the file path is within MEDIA_ROOT
        # Use is_relative_to for Python 3.9+, fallback for older versions
        try:
            return file_path_resolved.is_relative_to(media_root)
        except AttributeError:
            # Python < 3.9: use string comparison
            file_str = str(file_path_resolved)
            media_str = str(media_root)
            return file_str.startswith(media_str + os.sep) or file_str == media_str
    except Exception:
        # If we can't determine, err on the side of caution and exclude it
        # This could happen if MEDIA_ROOT is not set or path resolution fails
        return True


def is_image_file(file_path: Path, *, raw_only: bool = False) -> bool:
    """Check if a file is an image based on its extension.

    Args:
        file_path: Path to the file to check
        raw_only: When True, only camera RAW extensions are accepted.

    Returns:
        True if the file has an image extension, False otherwise
    """
    extensions = RAW_IMAGE_EXTENSIONS if raw_only else IMAGE_EXTENSIONS
    return file_path.suffix.lower() in extensions


def get_image_files(
    path: str,
    recursive: bool = True,
    media_root: Optional[Path] = None,
    raw_only: bool = False,
) -> List[Path]:
    """Get all image files from a directory.

    Excludes files that are within the Django MEDIA_ROOT directory to prevent
    ingestion loops where thumbnails stored in MEDIA_ROOT would be re-ingested.

    Args:
        path: Path to directory or file
        recursive: Whether to search recursively
        raw_only: When True, include only camera RAW extensions.

    Returns:
        List of Path objects for image files (excluding those in MEDIA_ROOT)
    """
    if media_root is None:
        media_root = _resolved_media_root()

    path_obj = Path(path)
    image_files = []

    def _in_media_root(file_path: Path) -> bool:
        return is_path_in_media_root(file_path, media_root=media_root)

    if path_obj.is_file():
        # Single file
        if is_image_file(path_obj, raw_only=raw_only) and not _in_media_root(path_obj):
            image_files.append(path_obj)
    elif path_obj.is_dir():
        # Directory
        if recursive:
            # Recursive search
            for root, dirs, files in os.walk(path):
                # Skip directories that are within MEDIA_ROOT
                root_path = Path(root)
                if _in_media_root(root_path):
                    # Skip this directory and all subdirectories
                    dirs[:] = []
                    continue

                for file in files:
                    file_path = Path(root) / file
                    if is_image_file(
                        file_path, raw_only=raw_only
                    ) and not _in_media_root(file_path):
                        image_files.append(file_path)
        else:
            # Non-recursive search
            for file in path_obj.iterdir():
                if (
                    file.is_file()
                    and is_image_file(file, raw_only=raw_only)
                    and not _in_media_root(file)
                ):
                    image_files.append(file)
    else:
        raise ValueError(f"Path does not exist or is not a file/directory: {path}")

    return image_files


def stored_path_for_file(
    file_path: Path,
    *,
    mount_point: Optional[str] = None,
    mount_table: Optional[List[str]] = None,
) -> str:
    """Return the path string stored on ``PhotoPath`` for a file on disk."""
    file_path_str = str(file_path.resolve())
    effective_mount = mount_point
    if effective_mount is None and mount_table is not None:
        effective_mount = mount_point_for_path(file_path_str, mount_table)
    elif effective_mount is None:
        effective_mount = get_mount_point(file_path_str)
    if effective_mount:
        mount_path = Path(effective_mount)
        file_path_obj = Path(file_path_str)
        try:
            return str(file_path_obj.relative_to(mount_path))
        except ValueError:
            return file_path_str
    return file_path_str


def _resolve_mount_for_file(
    file_path_str: str,
    mount_table: List[str],
    ingest_mount: Optional[str],
) -> Optional[str]:
    if ingest_mount and (
        file_path_str == ingest_mount or file_path_str.startswith(ingest_mount + os.sep)
    ):
        return ingest_mount
    return mount_point_for_path(file_path_str, mount_table)


_PATH_LOOKUP_CHUNK = 5000


def _stored_path_prefix_for_ingest(
    ingest_path: str,
    mount_table: List[str],
    ingest_mount: Optional[str],
) -> Optional[str]:
    ingest_resolved = Path(ingest_path).resolve()
    stored = stored_path_for_file(
        ingest_resolved,
        mount_point=ingest_mount,
        mount_table=mount_table,
    )
    if len(stored) < 2:
        return None
    if ingest_resolved.is_dir():
        return stored.rstrip("/") + "/"
    return stored


def _fetch_existing_catalog_paths(
    device: str,
    stored_paths: List[str],
    path_prefix: Optional[str],
) -> set[str]:
    n = len(stored_paths)
    if path_prefix and len(path_prefix) >= 2:
        prefix_count = PhotoPath.objects.filter(
            device=device, path__startswith=path_prefix
        ).count()
        if prefix_count <= n:
            return set(
                PhotoPath.objects.filter(
                    device=device, path__startswith=path_prefix
                ).values_list("path", flat=True)
            )
    existing: set[str] = set()
    for i in range(0, n, _PATH_LOOKUP_CHUNK):
        chunk = stored_paths[i : i + _PATH_LOOKUP_CHUNK]
        existing.update(
            PhotoPath.objects.filter(device=device, path__in=chunk).values_list(
                "path", flat=True
            )
        )
    return existing


def _fetch_photo_paths_by_stored_paths(
    device: str,
    stored_paths: List[str],
    path_prefix: Optional[str],
) -> Dict[str, Any]:
    """Map stored path strings to ``PhotoPath`` rows (with photograph prefetched)."""
    n = len(stored_paths)
    stored_set = set(stored_paths)
    by_path: Dict[str, Any] = {}

    if path_prefix and len(path_prefix) >= 2:
        prefix_count = PhotoPath.objects.filter(
            device=device, path__startswith=path_prefix
        ).count()
        if prefix_count <= n:
            for photo_path in PhotoPath.objects.filter(
                device=device, path__startswith=path_prefix
            ).select_related("photograph"):
                if photo_path.path in stored_set:
                    by_path[photo_path.path] = photo_path
            return by_path

    for i in range(0, n, _PATH_LOOKUP_CHUNK):
        chunk = stored_paths[i : i + _PATH_LOOKUP_CHUNK]
        for photo_path in PhotoPath.objects.filter(
            device=device, path__in=chunk
        ).select_related("photograph"):
            by_path[photo_path.path] = photo_path
    return by_path


def collect_thumbnail_retry_candidates(
    image_files: List[Path],
    device: str,
    *,
    ingest_path: str,
    mount_table: Optional[List[str]] = None,
    ingest_mount: Optional[str] = None,
    media_root: Optional[Path] = None,
) -> List[Tuple[Path, Any]]:
    """Return on-disk files that are catalogued on *device* but lack a thumbnail."""
    if mount_table is None:
        mount_table = load_mount_table()
    eligible: List[Tuple[Path, str]] = []
    for file_path in image_files:
        if is_path_in_media_root(file_path, media_root=media_root):
            continue
        eligible.append(
            (
                file_path,
                stored_path_for_file(file_path, mount_table=mount_table),
            )
        )

    if not eligible:
        return []

    stored_paths = [path_to_store for _, path_to_store in eligible]
    path_prefix = _stored_path_prefix_for_ingest(ingest_path, mount_table, ingest_mount)
    by_path = _fetch_photo_paths_by_stored_paths(device, stored_paths, path_prefix)

    candidates: List[Tuple[Path, Any]] = []
    for file_path, path_to_store in eligible:
        existing_path = by_path.get(path_to_store)
        if not existing_path:
            continue
        photograph = existing_path.photograph
        if photograph and not photograph.thumbnail:
            candidates.append((file_path, existing_path))
    return candidates


def filter_uningested_image_files(
    image_files: List[Path],
    device: str,
    *,
    ingest_path: str,
    mount_table: List[str],
    ingest_mount: Optional[str] = None,
    media_root: Optional[Path] = None,
) -> Tuple[List[Tuple[Path, str]], int]:
    """Return on-disk image files not yet catalogued on *device*.

    Returns:
        Tuple of (pending (path, stored_path) pairs, count skipped as already catalogued).
    """
    eligible: List[Tuple[Path, str]] = []
    for file_path in image_files:
        if is_path_in_media_root(file_path, media_root=media_root):
            continue
        eligible.append(
            (
                file_path,
                stored_path_for_file(file_path, mount_table=mount_table),
            )
        )

    if not eligible:
        return [], 0

    stored_paths = [path_to_store for _, path_to_store in eligible]
    path_prefix = _stored_path_prefix_for_ingest(ingest_path, mount_table, ingest_mount)
    existing = _fetch_existing_catalog_paths(device, stored_paths, path_prefix)

    pending: List[Tuple[Path, str]] = []
    skipped = 0
    for file_path, path_to_store in eligible:
        if path_to_store in existing:
            skipped += 1
        else:
            pending.append((file_path, path_to_store))
    return pending, skipped


def ingest_photos(
    path: str,
    resolution: Optional[str] = None,
    calculate_checksum: bool = True,
    recursive: bool = True,
    device: Optional[str] = None,
    store_images: bool = False,
    log_path: Optional[str] = None,
    retry_thumbnails: bool = False,
    raw_only: bool = False,
) -> Dict[str, Any]:
    """Ingest photos from a directory and store them in the database.

    This function:
    1. Finds all image files in the given path (recursively or not)
    2. Recognizes which files are pictures
    3. Calculates and stores a checksum for each photo (unless disabled)
    4. Optionally stores image files in the database
    5. Creates PhotoPath models (which automatically create/link Photograph models)

    Each photo is persisted to the database immediately after processing to avoid
    creating orphaned files in the media directory if the process is aborted.

    Args:
        path: Path to directory or file to ingest
        resolution: Optional resolution for the image. Can be explicit (e.g., '1920x1080')
            or a preset name (e.g., 'low', 'medium', 'high'). Images will be resized
            to this resolution when processed through backends. If store_images is True,
            images will be stored at this resolution.
        calculate_checksum: Whether to calculate and store a checksum for each photo (default: True)
        recursive: Whether to search subdirectories recursively
        device: Device identifier (defaults to hostname)
        store_images: Whether to store image files in the Photograph's image field.
            If True, images will be copied to the media directory. If resolution is
            specified, images will be resized accordingly.
        log_path: Optional path to log file where detailed error information will be written.
            If provided, all errors will be logged with full traceback information.
        retry_thumbnails: If True, do not create new catalog rows; for files that
            already exist as PhotoPath (same path and device), attempt thumbnail
            storage when the linked Photograph has no thumbnail.
        raw_only: When True, ingest only camera RAW file extensions.

    Returns:
        Dictionary with:
            - success: bool indicating if ingestion was successful
            - count: number of photos ingested
            - checksums_calculated: number of checksums calculated
            - images_stored: number of images stored (if store_images=True)
            - thumbnails_retried: number of existing catalog entries thumbnail-retry was attempted on
            - skipped_already_ingested: files already in the catalog for this device (not processed)
            - errors: list of error messages
    """
    if retry_thumbnails:
        store_images = True

    result = {
        "success": True,
        "count": 0,
        "checksums_calculated": 0,
        "images_stored": 0,
        "thumbnails_retried": 0,
        "skipped_already_ingested": 0,
        "errors": [],
    }

    if not HAS_DJANGO_BACKEND:
        raise ImportError(
            "Django backend models not available.\n "
            "Please, run using the Django shell:\n"
            "`python manage.py shell [-i ipython]`"
        )

    # Set up logger if log path is provided
    logger = _setup_logger(log_path)
    if logger:
        logger.info(f"Starting photo ingestion from: {path}")
        logger.info(
            f"Parameters: resolution={resolution}, calculate_checksum={calculate_checksum}, "
            f"recursive={recursive}, store_images={store_images}, "
            f"retry_thumbnails={retry_thumbnails}, raw_only={raw_only}"
        )

    try:
        # Get device name from the path being ingested
        # This identifies the filesystem/device where files are stored
        if device is None:
            device = get_device_name(path)

        # Parse resolution if provided
        resolution_tuple: Optional[Tuple[int, int]] = None
        if resolution:
            resolution_tuple = parse_resolution(resolution)
            if resolution_tuple is None:
                result["errors"].append(
                    f"Invalid resolution format: '{resolution}'. "
                    "Use format 'WIDTHxHEIGHT' or a preset name (e.g., 'low', 'medium', 'high')"
                )
                # Continue anyway, just without resolution processing

        mount_table = load_mount_table()
        ingest_mount = mount_point_for_path(str(Path(path).resolve()), mount_table)
        media_root = _resolved_media_root()

        # Get all image files
        image_files = get_image_files(
            path,
            recursive=recursive,
            media_root=media_root,
            raw_only=raw_only,
        )

        if not image_files:
            if raw_only:
                result["errors"].append(f"No raw image files found in: {path}")
            else:
                result["errors"].append(f"No image files found in: {path}")
            result["success"] = False
            return result

        if retry_thumbnails:
            retry_candidates = collect_thumbnail_retry_candidates(
                image_files,
                device,
                ingest_path=path,
                mount_table=mount_table,
                ingest_mount=ingest_mount,
                media_root=media_root,
            )
            if logger:
                logger.info(
                    "Thumbnail retry: %s catalogued file(s) missing thumbnails "
                    "(of %s image file(s) scanned)",
                    len(retry_candidates),
                    len(image_files),
                )
            resolution_arg = (
                resolution_tuple if resolution_tuple is not None else resolution
            )
            with tqdm(
                total=len(retry_candidates),
                desc="Retrying thumbnails",
                unit="file",
                unit_scale=False,
                dynamic_ncols=True,
            ) as pbar:
                for file_path, existing_path in retry_candidates:
                    file_path_str = str(file_path.resolve())
                    photograph = existing_path.photograph
                    try:
                        with transaction.atomic():
                            pbar.set_postfix_str(
                                os.path.basename(file_path_str)[:50], refresh=False
                            )
                            result["thumbnails_retried"] += 1
                            try:
                                success = photograph.get_image_from_file(
                                    file_path_str,
                                    resolution=resolution_arg,
                                )
                                if success:
                                    result["images_stored"] += 1
                                else:
                                    error_msg = (
                                        f"Failed to store thumbnail for {file_path_str}: "
                                        "get_image_from_file() returned False or no "
                                        "thumbnail was created."
                                    )
                                    result["errors"].append(error_msg)
                                    if logger:
                                        logger.warning(
                                            "Thumbnail retry failed for file: "
                                            f"{file_path_str}",
                                            extra={
                                                "file_path": file_path_str,
                                                "photograph_id": photograph.id,
                                            },
                                        )
                            except Exception as thumb_exc:
                                error_msg = (
                                    f"Error retrying thumbnail for {file_path_str}: "
                                    f"{thumb_exc}"
                                )
                                result["errors"].append(error_msg)
                                if logger:
                                    logger.error(
                                        f"Thumbnail retry error for file: {file_path_str}",
                                        exc_info=True,
                                        extra={"file_path": file_path_str},
                                    )
                    except Exception as e:
                        error_msg = f"Error processing {file_path}: {str(e)}"
                        result["errors"].append(error_msg)
                        if logger:
                            logger.error(
                                f"Error processing file: {file_path}",
                                exc_info=True,
                                extra={"file_path": str(file_path)},
                            )
                    pbar.update(1)

            if result["errors"]:
                if result["images_stored"] == 0:
                    result["success"] = False

            if logger:
                logger.info(
                    f"Ingestion completed. Success: {result['success']}, "
                    f"Count: {result['count']}, Errors: {len(result['errors'])}"
                )
            return result

        pending_files, skipped = filter_uningested_image_files(
            image_files,
            device,
            ingest_path=path,
            mount_table=mount_table,
            ingest_mount=ingest_mount,
            media_root=media_root,
        )
        result["skipped_already_ingested"] = skipped
        if logger:
            logger.info(
                "Skipping %s already catalogued file(s) (%s pending)",
                skipped,
                len(pending_files),
            )

        # Process each image file with progress bar
        # Use tqdm to show progress across pending files only
        with tqdm(
            total=len(pending_files),
            desc="Ingesting photos",
            unit="file",
            unit_scale=False,
            dynamic_ncols=True,
        ) as pbar:
            for file_path, path_to_store in pending_files:
                # Use a transaction per file to ensure each file is persisted immediately
                # This prevents orphaned files in the media directory if the process is aborted
                try:
                    with transaction.atomic():
                        file_path_str = str(file_path.resolve())

                        # Safety check: Never ingest files from MEDIA_ROOT
                        # This prevents loops where thumbnails stored in MEDIA_ROOT would be re-ingested
                        if is_path_in_media_root(file_path, media_root=media_root):
                            # Skip this file silently - it's in the media directory
                            pbar.update(1)
                            continue

                        # Update progress bar description with current file name
                        pbar.set_postfix_str(
                            os.path.basename(file_path_str)[:50], refresh=False
                        )

                        mount_point = _resolve_mount_for_file(
                            file_path_str, mount_table, ingest_mount
                        )

                        # If checksum calculation is requested, do it before creating PhotoPath
                        # This way the Photograph will be created with the checksum
                        photograph = None
                        if calculate_checksum:
                            checksum_value = calculate_file_checksum(file_path_str)
                            if checksum_value:
                                # Check if Photograph with this checksum exists
                                photograph, created = Photograph.objects.get_or_create(
                                    checksum=checksum_value, defaults={}
                                )
                                result["checksums_calculated"] += 1

                        # Create PhotoPath
                        # Note: The save() method will automatically create/link Photograph
                        # if the file exists and no photograph is set. If we already have
                        # a photograph (from checksum calculation), it will be used.
                        # We store the relative path (or absolute for root filesystem)
                        # but need to pass the full path to save() for file access
                        # Extract filename from the path (last component)
                        filename = (
                            os.path.basename(path_to_store) if path_to_store else None
                        )
                        photo_path = PhotoPath(
                            path=path_to_store,
                            filename=filename,
                            device=device,
                            photograph=photograph,
                        )

                        # Set file size if file exists
                        if os.path.exists(file_path_str):
                            try:
                                photo_path.size = os.path.getsize(file_path_str)
                            except (OSError, ValueError):
                                # If we can't get file size, leave it as None
                                pass

                        # Pass the full path for file access, but store the relative path
                        photo_path.save(
                            store_image=store_images,
                            resolution=resolution,
                            full_path=file_path_str if mount_point else None,
                        )

                        # Refresh photograph from database to get latest has_errors value
                        # (it may have been set in a transaction)
                        if photo_path.photograph:
                            photo_path.photograph.refresh_from_db()

                        # Check for errors that were silently caught in model methods
                        if photo_path.photograph and photo_path.photograph.has_errors:
                            error_msg = (
                                f"Error processing {file_path_str}: "
                                "Photograph has_errors flag is set. "
                                "This indicates an error occurred during image processing, "
                                "EXIF extraction, or checksum computation."
                            )
                            result["errors"].append(error_msg)

                            # Log detailed error information if logger is available
                            if logger:
                                logger.error(
                                    f"Error detected for file: {file_path_str} - "
                                    f"Photograph ID: {photo_path.photograph.id}, "
                                    f"has_errors=True. "
                                    f"This error was caught silently in model methods. "
                                    f"Possible causes: EXIF extraction failure, "
                                    f"checksum computation failure, or image processing error.",
                                    extra={
                                        "file_path": file_path_str,
                                        "photograph_id": photo_path.photograph.id,
                                        "has_errors": True,
                                    },
                                )

                        # Check if image storage was requested but failed
                        if store_images and photo_path.photograph:
                            if not photo_path.photograph.thumbnail:
                                error_msg = (
                                    f"Failed to store thumbnail for {file_path_str}: "
                                    "get_image_from_file() returned False or no thumbnail was created."
                                )
                                result["errors"].append(error_msg)

                                # Log detailed error information if logger is available
                                if logger:
                                    logger.warning(
                                        f"Thumbnail storage failed for file: {file_path_str}",
                                        extra={
                                            "file_path": file_path_str,
                                            "photograph_id": photo_path.photograph.id,
                                        },
                                    )

                        # Count images stored if requested
                        if (
                            store_images
                            and photo_path.photograph
                            and photo_path.photograph.thumbnail
                        ):
                            result["images_stored"] += 1

                        result["count"] += 1
                        # Transaction commits here automatically when exiting the context
                        pbar.update(1)

                except Exception as e:
                    error_msg = f"Error processing {file_path}: {str(e)}"
                    result["errors"].append(error_msg)

                    # Log detailed error information if logger is available
                    if logger:
                        logger.error(
                            f"Error processing file: {file_path}",
                            exc_info=True,
                            extra={"file_path": str(file_path)},
                        )

                    pbar.update(1)
                    # Continue processing other files

        if result["errors"]:
            # Some errors occurred but we may have processed some files
            if result["count"] == 0:
                result["success"] = False

    except Exception as e:
        result["success"] = False
        error_msg = f"Error during ingestion: {str(e)}"
        result["errors"].append(error_msg)

        # Log detailed error information if logger is available
        if logger:
            logger.critical(
                f"Critical error during ingestion: {error_msg}",
                exc_info=True,
                extra={"ingestion_path": path},
            )

    # Log completion summary if logger is available
    if logger:
        logger.info(
            f"Ingestion completed. Success: {result['success']}, "
            f"Count: {result['count']}, Errors: {len(result['errors'])}"
        )

    return result
