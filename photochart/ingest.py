"""Photo ingestion functionality.

This module provides functions for ingesting photos from directories,
calculating hashes, and storing them in the database.
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

from photochart.protocols import calculate_hash as calculate_file_hash
from photochart.resolution import parse_resolution
from photochart.device import get_device_name, get_mount_point

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


def is_path_in_media_root(file_path: Path) -> bool:
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
        media_root = Path(settings.MEDIA_ROOT).resolve()
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


# Common image file extensions
IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".tiff",
    ".tif",
    ".webp",
    ".heic",
    ".heif",
    ".raw",
    ".cr2",
    ".nef",
    ".orf",
    ".sr2",
    ".arw",
    ".dng",
    ".raf",
    ".rw2",
    ".pef",
    ".srw",
    ".3fr",
    ".mef",
    ".mos",
    ".ari",
    ".bay",
    ".crw",
    ".cap",
    ".dcs",
    ".dcr",
    ".drf",
    ".eip",
    ".erf",
    ".fff",
    ".iiq",
    ".k25",
    ".kdc",
    ".mdc",
    ".mrw",
    ".nrw",
    ".obm",
    ".pbm",
    ".pxn",
    ".r3d",
    ".raf",
    ".rwl",
    ".rwz",
    ".x3f",
    ".srf",
    ".srw",
    ".x3f",
}


def is_image_file(file_path: Path) -> bool:
    """Check if a file is an image based on its extension.

    Args:
        file_path: Path to the file to check

    Returns:
        True if the file has an image extension, False otherwise
    """
    return file_path.suffix.lower() in IMAGE_EXTENSIONS


def get_image_files(path: str, recursive: bool = True) -> List[Path]:
    """Get all image files from a directory.

    Excludes files that are within the Django MEDIA_ROOT directory to prevent
    ingestion loops where thumbnails stored in MEDIA_ROOT would be re-ingested.

    Args:
        path: Path to directory or file
        recursive: Whether to search recursively

    Returns:
        List of Path objects for image files (excluding those in MEDIA_ROOT)
    """
    path_obj = Path(path)
    image_files = []

    if path_obj.is_file():
        # Single file
        if is_image_file(path_obj) and not is_path_in_media_root(path_obj):
            image_files.append(path_obj)
    elif path_obj.is_dir():
        # Directory
        if recursive:
            # Recursive search
            for root, dirs, files in os.walk(path):
                # Skip directories that are within MEDIA_ROOT
                root_path = Path(root)
                if is_path_in_media_root(root_path):
                    # Skip this directory and all subdirectories
                    dirs[:] = []
                    continue

                for file in files:
                    file_path = Path(root) / file
                    if is_image_file(file_path) and not is_path_in_media_root(
                        file_path
                    ):
                        image_files.append(file_path)
        else:
            # Non-recursive search
            for file in path_obj.iterdir():
                if (
                    file.is_file()
                    and is_image_file(file)
                    and not is_path_in_media_root(file)
                ):
                    image_files.append(file)
    else:
        raise ValueError(f"Path does not exist or is not a file/directory: {path}")

    return image_files


def ingest_photos(
    path: str,
    resolution: Optional[str] = None,
    calculate_hash: bool = False,
    recursive: bool = True,
    device: Optional[str] = None,
    store_images: bool = False,
    log_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Ingest photos from a directory and store them in the database.

    This function:
    1. Finds all image files in the given path (recursively or not)
    2. Recognizes which files are pictures
    3. Calculates hash if instructed
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
        calculate_hash: Whether to calculate and store hash for each photo
        recursive: Whether to search subdirectories recursively
        device: Device identifier (defaults to hostname)
        store_images: Whether to store image files in the Photograph's image field.
            If True, images will be copied to the media directory. If resolution is
            specified, images will be resized accordingly.
        log_path: Optional path to log file where detailed error information will be written.
            If provided, all errors will be logged with full traceback information.

    Returns:
        Dictionary with:
            - success: bool indicating if ingestion was successful
            - count: number of photos ingested
            - hashes_calculated: number of hashes calculated
            - images_stored: number of images stored (if store_images=True)
            - errors: list of error messages
    """
    result = {
        "success": True,
        "count": 0,
        "hashes_calculated": 0,
        "images_stored": 0,
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
            f"Parameters: resolution={resolution}, calculate_hash={calculate_hash}, "
            f"recursive={recursive}, store_images={store_images}"
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

        # Get all image files
        image_files = get_image_files(path, recursive=recursive)

        if not image_files:
            result["errors"].append(f"No image files found in: {path}")
            result["success"] = False
            return result

        # Process each image file with progress bar
        # Use tqdm to show progress across all files (including nested ones) in a single bar
        with tqdm(
            total=len(image_files),
            desc="Ingesting photos",
            unit="file",
            unit_scale=False,
            dynamic_ncols=True,
        ) as pbar:
            for file_path in image_files:
                # Use a transaction per file to ensure each file is persisted immediately
                # This prevents orphaned files in the media directory if the process is aborted
                try:
                    with transaction.atomic():
                        file_path_str = str(file_path.resolve())

                        # Safety check: Never ingest files from MEDIA_ROOT
                        # This prevents loops where thumbnails stored in MEDIA_ROOT would be re-ingested
                        if is_path_in_media_root(file_path):
                            # Skip this file silently - it's in the media directory
                            pbar.update(1)
                            continue

                        # Update progress bar description with current file name
                        pbar.set_postfix_str(
                            os.path.basename(file_path_str)[:50], refresh=False
                        )

                        # For files on mounted devices, store path relative to mount point
                        # For files on root filesystem, store absolute path
                        mount_point = get_mount_point(file_path_str)
                        if mount_point:
                            # Calculate relative path from mount point
                            mount_path = Path(mount_point)
                            file_path_obj = Path(file_path_str)
                            try:
                                path_to_store = str(
                                    file_path_obj.relative_to(mount_path)
                                )
                            except ValueError:
                                # If relative_to fails, fall back to absolute path
                                path_to_store = file_path_str
                        else:
                            # On root filesystem, store absolute path
                            path_to_store = file_path_str

                        # Check if PhotoPath already exists for this path and device
                        existing_path = PhotoPath.objects.filter(
                            path=path_to_store, device=device
                        ).first()

                        if existing_path:
                            # Skip if already exists
                            pbar.update(1)
                            continue

                        # If hash calculation is requested, do it before creating PhotoPath
                        # This way the Photograph will be created with the hash
                        photograph = None
                        if calculate_hash:
                            hash_value = calculate_file_hash(file_path_str)
                            if hash_value:
                                # Check if Photograph with this hash exists
                                photograph, created = Photograph.objects.get_or_create(
                                    hash=hash_value, defaults={}
                                )
                                result["hashes_calculated"] += 1

                        # Create PhotoPath
                        # Note: The save() method will automatically create/link Photograph
                        # if the file exists and no photograph is set. If we already have
                        # a photograph (from hash calculation), it will be used.
                        # We store the relative path (or absolute for root filesystem)
                        # but need to pass the full path to save() for file access
                        photo_path = PhotoPath(
                            path=path_to_store,
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
                                "EXIF extraction, or hash computation."
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
                                    f"hash computation failure, or image processing error.",
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
