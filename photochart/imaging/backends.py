"""Image backends for processing different image file formats.

This module provides a backend system for handling various image formats,
including RAW formats that require special processing via rawpy.
"""

import os
import io
from pathlib import Path
from typing import Optional, Protocol, Dict, Type
from logging import Logger

from photochart.common.log import get_logger
from photochart.media.extensions import RAW_IMAGE_EXTENSIONS

LOGGER = get_logger(__name__)


class ImageBackend(Protocol):
    """Protocol for image processing backends.

    Backends should implement methods to process image files that cannot
    be handled by standard image libraries like PIL/Pillow.
    """

    def can_process(self, file_path: str) -> bool:
        """Check if this backend can process the given file.

        Args:
            file_path: Path to the image file

        Returns:
            True if this backend can process the file, False otherwise
        """
        ...

    def process_to_standard_format(
        self,
        file_path: str,
        output_format: str = "JPEG",
        resolution: Optional[tuple[int, int]] = None,
    ) -> Optional[io.BytesIO]:
        """Process the image file and return it as a standard format.

        Args:
            file_path: Path to the image file to process
            output_format: Desired output format (e.g., "JPEG", "PNG")
            resolution: Optional target resolution as (width, height) tuple

        Returns:
            BytesIO object containing the processed image, or None if processing fails
        """
        ...


class RawPyBackend:
    """Backend for camera RAW files supported by rawpy.

    Uses rawpy to extract embedded JPEG previews or convert RAW data to a
    standard image format. The embedded preview is preferred when available.
    """

    def __init__(self, logger: Logger = LOGGER):
        """Initialize the RAW backend.

        Args:
            logger: Logger instance for error reporting
        """
        self.logger = logger
        self._rawpy_available = self._check_rawpy_availability()

    def _check_rawpy_availability(self) -> bool:
        """Check if rawpy is available.

        Returns:
            True if rawpy can be imported, False otherwise
        """
        try:
            import rawpy  # noqa: F401

            return True
        except ImportError:
            self.logger.warning(
                "rawpy is not available. RAW file processing will be disabled. "
                "Install it with: pip install rawpy"
            )
            return False

    def can_process(self, file_path: str) -> bool:
        """Check if this backend can process the given file.

        Args:
            file_path: Path to the image file

        Returns:
            True if the file is a supported RAW format and rawpy is available
        """
        if not self._rawpy_available:
            return False

        path = Path(file_path)
        return path.suffix.lower() in RAW_IMAGE_EXTENSIONS and os.path.exists(file_path)

    def process_to_standard_format(
        self,
        file_path: str,
        output_format: str = "JPEG",
        resolution: Optional[tuple[int, int]] = None,
    ) -> Optional[io.BytesIO]:
        """Process a RAW file and return it as a standard format.

        This method first tries to extract the embedded JPEG preview from the file,
        which is faster and doesn't require full RAW processing. If that fails,
        it falls back to processing the RAW data.

        Args:
            file_path: Path to the RAW file
            output_format: Desired output format (default: "JPEG")
            resolution: Optional target resolution as (width, height) tuple

        Returns:
            BytesIO object containing the processed image, or None if processing fails
        """
        if not self._rawpy_available:
            self.logger.error(
                "rawpy is not available for processing RAW file: %s", file_path
            )
            return None

        if not os.path.exists(file_path):
            self.logger.error("RAW file does not exist: %s", file_path)
            return None

        try:
            import rawpy
            from PIL import Image

            with rawpy.imread(file_path) as raw:
                try:
                    thumb = raw.extract_thumb()
                    if thumb.format == rawpy.ThumbFormat.JPEG:
                        preview_data = thumb.data
                        image = Image.open(io.BytesIO(preview_data))
                        self.logger.debug(
                            "Extracted embedded JPEG preview from RAW file: %s",
                            file_path,
                        )
                    else:
                        image = Image.fromarray(thumb.data)
                        self.logger.debug(
                            "Extracted embedded preview (non-JPEG) from RAW file: %s",
                            file_path,
                        )
                except Exception as preview_error:
                    self.logger.debug(
                        "Could not extract preview from RAW file %s: %s. "
                        "Processing RAW data instead.",
                        file_path,
                        preview_error,
                    )
                    rgb_array = raw.postprocess()
                    image = Image.fromarray(rgb_array)

                output_buffer = io.BytesIO()
                if output_format.upper() == "JPEG":
                    if image.mode in ("RGBA", "LA", "P"):
                        rgb_image = Image.new("RGB", image.size, (255, 255, 255))
                        if image.mode == "P":
                            image = image.convert("RGBA")
                        rgb_image.paste(
                            image,
                            mask=image.split()[-1] if image.mode == "RGBA" else None,
                        )
                        image = rgb_image
                    elif image.mode not in ("RGB", "L"):
                        image = image.convert("RGB")

                if resolution:
                    target_width, target_height = resolution
                    original_width, original_height = image.size
                    aspect_ratio = original_width / original_height
                    target_aspect = target_width / target_height

                    if aspect_ratio > target_aspect:
                        new_width = target_width
                        new_height = int(target_width / aspect_ratio)
                    else:
                        new_height = target_height
                        new_width = int(target_height * aspect_ratio)

                    image = image.resize(
                        (new_width, new_height), Image.Resampling.LANCZOS
                    )
                    self.logger.debug(
                        "Resized image to %dx%d (requested: %dx%d)",
                        new_width,
                        new_height,
                        target_width,
                        target_height,
                    )

                if output_format.upper() == "JPEG":
                    image.save(output_buffer, format="JPEG", quality=95)
                else:
                    image.save(output_buffer, format=output_format)

                output_buffer.seek(0)
                self.logger.info("Successfully processed RAW file: %s", file_path)
                return output_buffer

        except Exception as exc:
            self.logger.error("Failed to process RAW file %s: %s", file_path, exc)
            return None


# Backwards-compatible alias
NEFBackend = RawPyBackend

# Backend registry
_BACKENDS: Dict[str, Type[ImageBackend]] = {}


def register_backend(extension: str, backend_class: Type[ImageBackend]) -> None:
    """Register an image backend for a specific file extension.

    Args:
        extension: File extension (e.g., ".nef") - should include the dot
        backend_class: Backend class that implements the ImageBackend protocol
    """
    from photochart.media.extensions import normalize_extension

    _BACKENDS[normalize_extension(extension)] = backend_class


def get_backend(file_path: str) -> Optional[ImageBackend]:
    """Get the appropriate backend for a given file path.

    Args:
        file_path: Path to the image file

    Returns:
        An instance of the appropriate backend, or None if no backend is available
    """
    path = Path(file_path)
    extension = path.suffix.lower()

    backend_class = _BACKENDS.get(extension)
    if backend_class is None:
        return None

    backend = backend_class()
    if backend.can_process(file_path):
        return backend

    return None


def process_image_file(
    file_path: str,
    output_format: str = "JPEG",
    resolution: Optional[tuple[int, int]] = None,
    logger: Logger = LOGGER,
) -> Optional[io.BytesIO]:
    """Process an image file using the appropriate backend.

    This function automatically selects the correct backend based on the file extension
    and processes the image to a standard format that can be used by Django's ImageField.

    Args:
        file_path: Path to the image file to process
        output_format: Desired output format (default: "JPEG")
        resolution: Optional target resolution as (width, height) tuple
        logger: Logger instance for error reporting

    Returns:
        BytesIO object containing the processed image, or None if processing fails
    """
    backend = get_backend(file_path)
    if backend is None:
        return None

    return backend.process_to_standard_format(file_path, output_format, resolution)


for _raw_extension in RAW_IMAGE_EXTENSIONS:
    register_backend(_raw_extension, RawPyBackend)
