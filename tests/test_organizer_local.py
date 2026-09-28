from datetime import datetime, timezone
from pathlib import Path

from photochart.organizer.adapters import LocalFilesystemAdapter
from photochart.organizer.config import OrganizerConfig
from photochart.organizer.domain import OperationStatus
from photochart.organizer.service import Organizer


def build_organizer(source: Path, destination: Path, mode: str = "move") -> Organizer:
    config = OrganizerConfig(
        source=str(source),
        destination=str(destination),
        mode=mode,
        pattern="%YQ%Q/%Y%M%D",
        stability=config_stability(),
    )
    return Organizer(LocalFilesystemAdapter(), config)


def config_stability():
    from photochart.organizer.config import StabilityConfig

    return StabilityConfig(interval_seconds=0, checks=1)


def set_date(path: Path) -> None:
    timestamp = datetime(2026, 9, 28, 12, tzinfo=timezone.utc).timestamp()
    path.touch()
    path.chmod(0o600)
    import os

    os.utime(path, (timestamp, timestamp))


def test_move_classifies_by_quarter_and_day(tmp_path: Path) -> None:
    source = tmp_path / "PhotoUpload"
    destination = tmp_path / "Photos"
    source.mkdir()
    photo = source / "photo.jpg"
    photo.write_bytes(b"photo")
    set_date(photo)

    results = build_organizer(source, destination).run_once()

    assert results[0].status == OperationStatus.MOVED
    assert (destination / "2026Q3" / "20260928" / "photo.jpg").read_bytes() == b"photo"
    assert not photo.exists()


def test_collision_suffixes_different_content(tmp_path: Path) -> None:
    source = tmp_path / "PhotoUpload"
    destination = tmp_path / "Photos"
    source.mkdir()
    existing = destination / "2026Q3" / "20260928" / "photo.jpg"
    existing.parent.mkdir(parents=True)
    existing.write_bytes(b"old")
    photo = source / "photo.jpg"
    photo.write_bytes(b"new")
    set_date(photo)

    result = build_organizer(source, destination).run_once()[0]

    assert result.destination is not None
    assert result.destination.endswith("photo_1.jpg")
    assert Path(result.destination).read_bytes() == b"new"


def test_dry_run_changes_nothing(tmp_path: Path) -> None:
    source = tmp_path / "PhotoUpload"
    destination = tmp_path / "Photos"
    source.mkdir()
    photo = source / "photo.jpg"
    photo.write_bytes(b"photo")
    set_date(photo)

    result = build_organizer(source, destination).run_once(dry_run=True)[0]

    assert result.status == OperationStatus.DRY_RUN
    assert photo.exists()
    assert not destination.exists()
