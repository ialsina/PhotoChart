"""Core file operation protocols for safe and efficient file handling.

This module provides a set of protocols for performing file operations with additional
safety checks and error handling. These protocols are designed to ensure data integrity
and provide atomic operations where possible.

Key features:
- File integrity verification through hash checking
- Space availability verification before operations
- Atomic file operations to prevent partial transfers
- Chunked file transfers for large files
- Comprehensive error handling and logging
"""

import os
import shutil
import hashlib
from logging import Logger
from typing import Optional

from .log import get_logger

LOGGER = get_logger(__name__)


def calculate_hash(path: str, logger: Logger = LOGGER) -> Optional[str]:
    """Calculate MD5 hash of a file for integrity checking.

    This function reads the file in chunks to handle large files efficiently
    and calculates an MD5 hash for integrity verification.

    Args:
        path: Path to the file to hash
        logger: Logger instance for error reporting

    Returns:
        MD5 hash as a hexadecimal string, or None if hashing fails

    Note:
        Uses a chunk size of 4096 bytes for efficient memory usage
    """
    hash_md5 = hashlib.md5()
    try:
        with open(path, "rb") as f:
            # Read file in chunks to handle large files efficiently
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception as exc:
        logger.error("Failed to calculate hash for %s: %s", path, exc)
        return None


def check_disk_space(path: str, required_size: int, logger: Logger = LOGGER) -> bool:
    """Check if the destination has enough space for the file.

    This function checks the available space on the filesystem where the
    specified path resides and compares it with the required size.

    Args:
        path: Path to check available space for
        required_size: Size in bytes required for the operation
        logger: Logger instance for error reporting

    Returns:
        True if enough space is available, False otherwise

    Note:
        Uses os.statvfs for Unix-like systems. May need adjustment for Windows.
    """
    try:
        stat = os.statvfs(path)
        # Calculate available space: blocks available * block size
        available_space = stat.f_bavail * stat.f_frsize
        return available_space >= required_size
    except Exception as exc:
        logger.error("Error checking disk space for %s: %s", path, exc)
        return False


def cp(
    src: str, dst: str, buffer_size: int = 1024 * 1024, logger: Logger = LOGGER
) -> None:
    """Copy a file in chunks with progress tracking and error handling.

    This function performs a chunked copy operation, which is essential for
    handling large files efficiently. It also preserves file metadata.

    Args:
        src: Source file path
        dst: Destination file path
        buffer_size: Size of chunks to read/write (default: 1MB)
        logger: Logger instance for operation tracking

    Raises:
        Exception: If the copy operation fails

    Note:
        Uses a default buffer size of 1MB for optimal performance
    """
    try:
        with open(src, "rb") as f_src, open(dst, "wb") as f_dst:
            # Copy file in chunks to handle large files efficiently
            while chunk := f_src.read(buffer_size):
                f_dst.write(chunk)
        # Preserve file metadata (permissions, timestamps, etc.)
        shutil.copystat(src, dst)
        logger.info("Successfully moved large file %s to %s", src, dst)
    except Exception as exc:
        logger.error("Error during chunked move from %s to %s: %s", src, dst, exc)
        raise exc


def mv(src: str, dst: str, logger: Logger = LOGGER) -> None:
    """Safely move a file with comprehensive checks and atomic operation.

    This function implements a safe file move operation with the following features:
    - Space availability verification
    - Atomic operation using temporary files
    - Integrity verification through hash checking
    - Comprehensive error handling and cleanup

    Args:
        src: Source file path
        dst: Destination file path
        logger: Logger instance for operation tracking

    Note:
        The operation is atomic - either the entire move succeeds or fails
        with no partial state. Temporary files are cleaned up in case of failure.
    """
    if not os.path.exists(src):
        logger.error("Source file does not exist: %s", src)
        return

    # Ensure the destination directory exists
    os.makedirs(os.path.dirname(dst), exist_ok=True)

    # Verify sufficient space at destination
    file_size = os.path.getsize(src)
    if not check_disk_space(os.path.dirname(dst), file_size):
        logger.error("Not enough space at destination %s", os.path.dirname(dst))
        return

    # Use temporary file for atomic operation
    temp_dst = dst + ".tmp"
    try:
        # Perform chunked copy to temporary location
        cp(src, temp_dst)

        # Verify file integrity through hash comparison
        src_hash = calculate_hash(src)
        dst_hash = calculate_hash(temp_dst)

        if src_hash and dst_hash and src_hash == dst_hash:
            logger.info("Integrity check passed for file %s", src)
            # Atomic rename to final destination
            os.rename(temp_dst, dst)
            # Remove source file only after successful move
            os.remove(src)
            logger.info("File successfully moved from %s to %s", src, dst)
        else:
            logger.error("Integrity check failed for file %s", src)
            # Clean up temporary file if integrity check fails
            os.remove(temp_dst)
    except Exception as exc:
        logger.error("Failed to move file %s to %s: %s", src, dst, exc)
        # Ensure temporary file is cleaned up in case of error
        if os.path.exists(temp_dst):
            os.remove(temp_dst)


def rm(path: str, logger: Logger = LOGGER) -> None:
    """Safely remove a file with logging.

    This function provides a safe way to remove files with proper error handling
    and logging of the operation.

    Args:
        path: Path to the file to remove
        logger: Logger instance for operation tracking
    """
    if os.path.exists(path):
        os.remove(path)
        logger.info("File successfully removed: %s", path)
    else:
        logger.error("File not found: %s", path)
