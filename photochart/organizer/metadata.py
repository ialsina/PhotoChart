"""Media metadata extraction and capture-date selection."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from .config import OrganizerConfig
from .domain import DateResult, MediaObject
from .storage import StorageAdapter


DATE_FORMATS = (
    "%Y:%m:%d %H:%M:%S%z",
    "%Y:%m:%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%d %H:%M:%S",
)


def _parse_date(value: Any, default_timezone: str) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        normalized = value.strip().replace("Z", "+00:00")
        parsed = None
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            for date_format in DATE_FORMATS:
                try:
                    parsed = datetime.strptime(normalized, date_format)
                    break
                except ValueError:
                    continue
        if parsed is None:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo(default_timezone))
    return parsed


def resolve_capture_date(
    metadata: Mapping[str, Any],
    media: MediaObject,
    config: OrganizerConfig,
) -> DateResult:
    current_year = datetime.now().year
    for field in config.date_priority:
        parsed = _parse_date(metadata.get(field), config.timezone)
        if parsed is not None and 1990 <= parsed.year <= current_year + 1:
            return DateResult(parsed, f"metadata:{field}", str(parsed.tzinfo), "high")
    if media.modified_time is not None:
        parsed = _parse_date(media.modified_time, config.timezone)
        if parsed is not None:
            return DateResult(
                parsed, "filesystem_modified_time", str(parsed.tzinfo), "fallback"
            )
    raise ValueError(f"No plausible capture date for {media.path}")


class MetadataExtractor:
    """Use ExifTool when available, with PhotoChart's image reader as fallback."""

    def inspect(self, adapter: StorageAdapter, media: MediaObject) -> Mapping[str, Any]:
        local_path, temporary = self._prepare_local(adapter, media)
        try:
            metadata = self._exiftool(local_path)
            if metadata:
                return metadata
            from photochart.imaging.extract import extract_metadata

            extracted = extract_metadata(local_path)
            return extracted.get("exif", {})
        finally:
            if temporary:
                Path(local_path).unlink(missing_ok=True)

    def _prepare_local(
        self, adapter: StorageAdapter, media: MediaObject
    ) -> tuple[str, bool]:
        if adapter.get_capabilities().local_filesystem:
            return media.path, False
        suffix = Path(media.name).suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temporary:
            with adapter.open_read(media.path) as source:
                shutil.copyfileobj(source, temporary)
            return temporary.name, True

    @staticmethod
    def _exiftool(path: str) -> Mapping[str, Any]:
        executable = shutil.which("exiftool")
        if executable is None:
            return {}
        completed = subprocess.run(
            [executable, "-json", "-n", path],
            capture_output=True,
            check=False,
            text=True,
            timeout=120,
        )
        if completed.returncode != 0:
            return {}
        payload = json.loads(completed.stdout)
        return payload[0] if payload else {}
