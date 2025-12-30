"""Photo ingestion functionality.

This module provides functions for ingesting photos from directories,
calculating hashes, and storing them in the database.
"""

import os
import socket
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

from django.conf import settings
from django.db import transaction
from tqdm import tqdm

from photograph.models import PhotoPath, Photograph
from photochart.protocols import calculate_hash as calculate_file_hash
from photochart.resolution import parse_resolution


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


def get_device_name(file_path: Optional[str] = None) -> str:
    """Get the device/filesystem identifier for a file path.

    Identifies the filesystem/device where files are stored, not just the hostname.
    For files on the root filesystem, returns the hostname. For files on mounted
    filesystems (external drives, network mounts, etc.), returns a device identifier
    such as mount point name, device label, or UUID.

    Args:
        file_path: Optional path to a file. If provided, determines the device
            for that specific path. If None, returns hostname for local filesystem.

    Returns:
        Device identifier string (hostname, mount point, device label, or 'unknown')
    """
    # If no path provided, return hostname for local filesystem
    if file_path is None:
        try:
            return socket.gethostname()
        except Exception:
            return "unknown"

    try:
        path_obj = Path(file_path)
        if not path_obj.exists():
            # Path doesn't exist, try to get device from parent directory
            path_obj = path_obj.parent
            while path_obj != path_obj.parent and not path_obj.exists():
                path_obj = path_obj.parent
            if not path_obj.exists():
                # Can't determine device, fall back to hostname
                try:
                    return socket.gethostname()
                except Exception:
                    return "unknown"

        # Resolve to absolute path
        abs_path = path_obj.resolve()

        # Try to find the mount point for this path
        mount_point = None
        device_info = None

        # Read /proc/mounts to find mount points (Linux)
        try:
            with open("/proc/mounts", "r") as f:
                mounts = []
                for line in f:
                    parts = line.split()
                    if len(parts) >= 2:
                        device = parts[0]
                        mount = parts[1]
                        fstype = parts[2] if len(parts) > 2 else ""
                        mounts.append((device, mount, fstype))

                # Sort by mount path length (longest first) to match most specific mount
                mounts.sort(key=lambda x: len(x[1]), reverse=True)

                # Find the mount point that contains our path
                for device, mount, fstype in mounts:
                    try:
                        mount_path = Path(mount)
                        if mount_path.exists() and abs_path.is_relative_to(mount_path):
                            mount_point = mount
                            device_info = (device, fstype)
                            break
                    except (ValueError, OSError):
                        # Path comparison failed, skip
                        continue
        except (OSError, IOError):
            # /proc/mounts not available (not Linux or permission issue)
            pass

        # If we found a mount point, try to identify the device
        if mount_point and device_info:
            device, fstype = device_info

            # Check if it's the root filesystem
            if mount_point == "/":
                try:
                    return socket.gethostname()
                except Exception:
                    return "local"

            # Try to get device label (for external drives)
            if device.startswith("/dev/"):
                device_name = device[5:]  # Remove /dev/ prefix

                # Try to find label in /dev/disk/by-label/
                try:
                    by_label = Path("/dev/disk/by-label")
                    if by_label.exists():
                        for label_link in by_label.iterdir():
                            try:
                                target = label_link.readlink()
                                if target.name == device_name or str(target) == device:
                                    # Found label, use it
                                    label = label_link.name
                                    # Decode URL-encoded labels (some filesystems use this)
                                    try:
                                        import urllib.parse

                                        label = urllib.parse.unquote(label)
                                    except Exception:
                                        pass
                                    return f"{label} ({mount_point})"
                            except (OSError, ValueError):
                                continue
                except (OSError, IOError):
                    pass

                # Try to find UUID in /dev/disk/by-uuid/
                try:
                    by_uuid = Path("/dev/disk/by-uuid")
                    if by_uuid.exists():
                        for uuid_link in by_uuid.iterdir():
                            try:
                                target = uuid_link.readlink()
                                if target.name == device_name or str(target) == device:
                                    uuid = uuid_link.name
                                    # Use mount point name with UUID for identification
                                    mount_name = Path(mount_point).name or mount_point
                                    return f"{mount_name} [{uuid[:8]}]"
                            except (OSError, ValueError):
                                continue
                except (OSError, IOError):
                    pass

                # For network filesystems, extract server/share info
                if fstype in ["nfs", "cifs", "smbfs"]:
                    # Extract server name from device string
                    # Format might be server:/path or //server/share
                    if ":" in device:
                        server = device.split(":")[0]
                        return f"{server} ({mount_point})"
                    elif device.startswith("//"):
                        parts = device[2:].split("/", 1)
                        server = parts[0] if parts else "network"
                        return f"{server} ({mount_point})"

                # Use device name with mount point
                mount_name = Path(mount_point).name or mount_point
                return f"{device_name} ({mount_name})"

            # For other device types, use mount point name
            mount_name = Path(mount_point).name or mount_point
            return mount_name

        # Fallback: check if path is on root filesystem
        # If we can't determine mount point, assume local filesystem
        try:
            return socket.gethostname()
        except Exception:
            return "local"

    except Exception:
        # If anything fails, fall back to hostname
        try:
            return socket.gethostname()
        except Exception:
            return "unknown"


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

                        # Check if PhotoPath already exists for this path and device
                        existing_path = PhotoPath.objects.filter(
                            path=file_path_str, device=device
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
                        photo_path = PhotoPath(
                            path=file_path_str,
                            device=device,
                            photograph=photograph,
                        )
                        # Pass store_image and resolution to save() method
                        photo_path.save(store_image=store_images, resolution=resolution)

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
                    pbar.update(1)
                    # Continue processing other files

        if result["errors"]:
            # Some errors occurred but we may have processed some files
            if result["count"] == 0:
                result["success"] = False

    except Exception as e:
        result["success"] = False
        result["errors"].append(f"Error during ingestion: {str(e)}")

    return result
