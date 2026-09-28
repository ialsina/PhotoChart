from datetime import datetime, timezone

from photochart.organizer.config import OrganizerConfig
from photochart.organizer.domain import MediaObject
from photochart.organizer.metadata import resolve_capture_date


def media(modified: datetime | None = None) -> MediaObject:
    return MediaObject("test", "1", "/photo.jpg", "photo.jpg", 10, modified)


def config() -> OrganizerConfig:
    return OrganizerConfig("/in", "/out", timezone="Europe/Madrid")


def test_prefers_original_capture_date() -> None:
    result = resolve_capture_date(
        {
            "DateTimeOriginal": "2024:07:08 09:10:11",
            "CreateDate": "2025:01:01 00:00:00",
        },
        media(),
        config(),
    )

    assert result.value == datetime.fromisoformat("2024-07-08T09:10:11+02:00")
    assert result.source == "metadata:DateTimeOriginal"


def test_rejects_implausible_metadata_and_uses_mtime() -> None:
    modified = datetime(2026, 9, 28, tzinfo=timezone.utc)

    result = resolve_capture_date(
        {"DateTimeOriginal": "0000:00:00 00:00:00"},
        media(modified),
        config(),
    )

    assert result.value == modified
    assert result.source == "filesystem_modified_time"
