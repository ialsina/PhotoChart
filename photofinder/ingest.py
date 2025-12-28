"""Photo ingestion functionality.

This module provides functions for ingesting photos from directories,
calculating hashes, and storing them in the database.
"""

import os
import socket
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

from django.db import transaction

from photograph.models import PhotoPath, Photograph
from photofinder.protocols import calculate_hash
from photofinder.resolution import parse_resolution


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


def get_device_name() -> str:
    """Get the current device/hostname.

    Returns:
        Device name (hostname) or 'unknown' if unavailable
    """
    try:
        return socket.gethostname()
    except Exception:
        return "unknown"


def get_image_files(path: str, recursive: bool = True) -> List[Path]:
    """Get all image files from a directory.

    Args:
        path: Path to directory or file
        recursive: Whether to search recursively

    Returns:
        List of Path objects for image files
    """
    path_obj = Path(path)
    image_files = []

    if path_obj.is_file():
        # Single file
        if is_image_file(path_obj):
            image_files.append(path_obj)
    elif path_obj.is_dir():
        # Directory
        if recursive:
            # Recursive search
            for root, dirs, files in os.walk(path):
                for file in files:
                    file_path = Path(root) / file
                    if is_image_file(file_path):
                        image_files.append(file_path)
        else:
            # Non-recursive search
            for file in path_obj.iterdir():
                if file.is_file() and is_image_file(file):
                    image_files.append(file)
    else:
        raise ValueError(f"Path does not exist or is not a file/directory: {path}")

    return image_files


@transaction.atomic
def ingest_photos(
    path: str,
    resolution: Optional[str] = None,
    calculate_hash: bool = False,
    recursive: bool = True,
    device: Optional[str] = None,
) -> Dict[str, Any]:
    """Ingest photos from a directory and store them in the database.

    This function:
    1. Finds all image files in the given path (recursively or not)
    2. Recognizes which files are pictures
    3. Calculates hash if instructed
    4. Creates PhotoPath models (which automatically create/link Photograph models)

    Args:
        path: Path to directory or file to ingest
        resolution: Optional resolution for the image. Can be explicit (e.g., '1920x1080')
            or a preset name (e.g., 'low', 'medium', 'high'). Images will be resized
            to this resolution when processed through backends.
        calculate_hash: Whether to calculate and store hash for each photo
        recursive: Whether to search subdirectories recursively
        device: Device identifier (defaults to hostname)

    Returns:
        Dictionary with:
            - success: bool indicating if ingestion was successful
            - count: number of photos ingested
            - hashes_calculated: number of hashes calculated
            - errors: list of error messages
    """
    result = {
        "success": True,
        "count": 0,
        "hashes_calculated": 0,
        "errors": [],
    }

    try:
        # Get device name
        if device is None:
            device = get_device_name()

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

        # Process each image file
        for file_path in image_files:
            try:
                file_path_str = str(file_path.resolve())

                # Check if PhotoPath already exists for this path and device
                existing_path = PhotoPath.objects.filter(
                    path=file_path_str, device=device
                ).first()

                if existing_path:
                    # Skip if already exists
                    continue

                # If hash calculation is requested, do it before creating PhotoPath
                # This way the Photograph will be created with the hash
                photograph = None
                if calculate_hash:
                    hash_value = calculate_hash(file_path_str)
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
                photo_path = PhotoPath(
                    path=file_path_str,
                    device=device,
                    photograph=photograph,
                )
                photo_path.save()

                result["count"] += 1

            except Exception as e:
                error_msg = f"Error processing {file_path}: {str(e)}"
                result["errors"].append(error_msg)
                # Continue processing other files

        if result["errors"]:
            # Some errors occurred but we may have processed some files
            if result["count"] == 0:
                result["success"] = False

    except Exception as e:
        result["success"] = False
        result["errors"].append(f"Error during ingestion: {str(e)}")

    return result
