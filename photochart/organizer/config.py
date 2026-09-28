"""Organizer configuration loading and validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

import yaml

from .patterns import ClassificationPattern


@dataclass(frozen=True)
class StabilityConfig:
    interval_seconds: float = 30
    checks: int = 2


@dataclass(frozen=True)
class RetryConfig:
    attempts: int = 4
    initial_seconds: float = 5
    multiplier: float = 3


@dataclass(frozen=True)
class OrganizerConfig:
    source: str
    destination: str
    adapter: str = "local"
    pattern: str = "%Y/%YQ%Q/%Y%M%D"
    quarantine: str | None = None
    timezone: str = "UTC"
    collision: str = "suffix"
    duplicate_detection: str = "size_then_hash"
    mode: str = "move"
    workers: int = 1
    process_after: datetime | None = None
    include_first: bool = True
    day_starts_at: float = 0
    media_extensions: tuple[str, ...] = field(
        default=(
            ".jpg",
            ".jpeg",
            ".heic",
            ".heif",
            ".png",
            ".tif",
            ".tiff",
            ".nef",
            ".dng",
            ".mp4",
            ".mov",
            ".m4v",
        )
    )
    date_priority: tuple[str, ...] = field(
        default=(
            "DateTimeOriginal",
            "SubSecDateTimeOriginal",
            "CreateDate",
            "MediaCreateDate",
            "TrackCreateDate",
            "ModifyDate",
        )
    )
    stability: StabilityConfig = field(default_factory=StabilityConfig)
    retry: RetryConfig = field(default_factory=RetryConfig)

    def __post_init__(self) -> None:
        ClassificationPattern(self.pattern)
        if not self.source or not self.destination:
            raise ValueError("source and destination are required")
        if self.mode not in {"copy", "move"}:
            raise ValueError("mode must be 'copy' or 'move'")
        if self.collision not in {"suffix", "fail", "quarantine"}:
            raise ValueError("unsupported collision policy")
        if self.workers < 1:
            raise ValueError("workers must be at least one")
        if not 0 <= self.day_starts_at < 24:
            raise ValueError("day_starts_at must be between 0 and 24")


def _nested(mapping: Mapping[str, Any], key: str, default: Any = None) -> Any:
    value = mapping.get(key, default)
    return value if isinstance(value, Mapping) else default


def config_from_mapping(data: Mapping[str, Any]) -> OrganizerConfig:
    adapter = _nested(data, "adapter", {})
    source = _nested(data, "source", {})
    destination = _nested(data, "destination", {})
    metadata = _nested(data, "metadata", {})
    stability = _nested(data, "stability", {})
    retry = _nested(data, "retry", {})
    media = _nested(data, "media", {})
    duplicate = _nested(data, "duplicate_detection", {})
    collision = _nested(data, "collision", {})
    date = _nested(data, "date", {})
    process_after = date.get("process_after")
    if isinstance(process_after, str):
        process_after = datetime.fromisoformat(process_after)

    return OrganizerConfig(
        source=str(source.get("path", data.get("source_path", ""))),
        destination=str(destination.get("path", data.get("destination_path", ""))),
        adapter=str(adapter.get("type", "local")),
        pattern=str(destination.get("pattern", "%Y/%YQ%Q/%Y%M%D")),
        quarantine=(
            data.get("quarantine", {}).get("path")
            if isinstance(data.get("quarantine"), Mapping)
            else None
        ),
        timezone=(
            str(data.get("timezone", {}).get("default", "UTC"))
            if isinstance(data.get("timezone"), Mapping)
            else str(data.get("timezone", "UTC"))
        ),
        collision=str(collision.get("mode", "suffix")),
        duplicate_detection=str(duplicate.get("mode", "size_then_hash")),
        mode=str(data.get("mode", "move")),
        workers=int(data.get("workers", 1)),
        process_after=process_after,
        include_first=bool(date.get("include_first", True)),
        day_starts_at=float(date.get("day_starts_at", 0)),
        media_extensions=tuple(
            extension.lower()
            for extension in media.get(
                "extensions",
                OrganizerConfig.__dataclass_fields__["media_extensions"].default,
            )
        ),
        date_priority=tuple(
            metadata.get(
                "date_priority",
                OrganizerConfig.__dataclass_fields__["date_priority"].default,
            )
        ),
        stability=StabilityConfig(
            interval_seconds=float(stability.get("interval_seconds", 30)),
            checks=int(stability.get("checks", 2)),
        ),
        retry=RetryConfig(
            attempts=int(retry.get("attempts", 4)),
            initial_seconds=float(retry.get("initial_seconds", 5)),
            multiplier=float(retry.get("multiplier", 3)),
        ),
    )


def load_config(path: str | Path) -> OrganizerConfig:
    with Path(path).expanduser().open("r", encoding="utf-8") as config_file:
        data = yaml.safe_load(config_file) or {}
    if not isinstance(data, Mapping):
        raise ValueError("Organizer configuration must be a mapping")
    return config_from_mapping(data)
