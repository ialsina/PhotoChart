from pathlib import Path

from photochart.organizer.adapters import LocalFilesystemAdapter
from photochart.organizer.reports import (
    find_duplicates,
    find_missing,
    storage_histogram,
)


def test_duplicate_groups_and_histogram(tmp_path: Path) -> None:
    (tmp_path / "a.jpg").write_bytes(b"same")
    (tmp_path / "b.jpg").write_bytes(b"same")
    (tmp_path / "different.jpg").write_bytes(b"other")

    groups = find_duplicates(LocalFilesystemAdapter(), str(tmp_path))

    assert len(groups) == 1
    assert {Path(path).name for path in groups[0].paths} == {"a.jpg", "b.jpg"}
    assert storage_histogram(groups) == {
        "duplicate_groups": 1,
        "duplicate_files": 1,
        "wasted_bytes": 4,
    }


def test_missing_report_matches_name_and_size(tmp_path: Path) -> None:
    origin = tmp_path / "origin"
    destination = tmp_path / "destination"
    origin.mkdir()
    destination.mkdir()
    (origin / "present.jpg").write_bytes(b"same")
    (destination / "present.jpg").write_bytes(b"same")
    (origin / "missing.jpg").write_bytes(b"missing")

    missing = find_missing(LocalFilesystemAdapter(), str(origin), str(destination))

    assert [Path(path).name for path in missing] == ["missing.jpg"]
