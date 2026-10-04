"""Explicit, verified metadata date correction."""

from __future__ import annotations

import shutil
import subprocess
from datetime import datetime
from pathlib import Path


from photochart.media.extensions import IMAGE_EXTENSIONS

SUPPORTED_EXTENSIONS = IMAGE_EXTENSIONS


def set_original_date(
    path: str | Path,
    value: datetime,
    *,
    dry_run: bool = True,
    backup: bool = True,
) -> str:
    media_path = Path(path).expanduser().resolve()
    if media_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported metadata format: {media_path.suffix}")
    if not media_path.is_file():
        raise FileNotFoundError(media_path)
    formatted = value.strftime("%Y:%m:%d %H:%M:%S")
    if dry_run:
        return f"WOULD SET DateTimeOriginal={formatted} on {media_path}"

    executable = shutil.which("exiftool")
    if executable is None:
        raise RuntimeError("ExifTool is required to edit metadata")
    arguments = [
        executable,
        f"-DateTimeOriginal={formatted}",
        f"-CreateDate={formatted}",
    ]
    if not backup:
        arguments.append("-overwrite_original")
    arguments.append(str(media_path))
    completed = subprocess.run(
        arguments, capture_output=True, check=False, text=True, timeout=120
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "ExifTool update failed")
    verify = subprocess.run(
        [executable, "-s3", "-DateTimeOriginal", str(media_path)],
        capture_output=True,
        check=False,
        text=True,
        timeout=120,
    )
    if verify.returncode != 0 or formatted not in verify.stdout:
        raise RuntimeError("Metadata update could not be verified")
    return f"SET DateTimeOriginal={formatted} on {media_path}"
