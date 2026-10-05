"""Tests for ingest stored-path helpers."""

from pathlib import Path

from photochart.ingest.photos import stored_path_for_file


def test_stored_path_uses_mount_table_without_reading_proc(tmp_path) -> None:
    mount = tmp_path / "mnt"
    mount.mkdir()
    dcim = mount / "DCIM"
    dcim.mkdir()
    photo = dcim / "a.jpg"
    photo.write_bytes(b"x")

    mount_table = [str(mount)]
    stored = stored_path_for_file(photo, mount_table=mount_table)
    assert stored == "DCIM/a.jpg"


def test_stored_path_with_explicit_mount_point(tmp_path) -> None:
    mount = tmp_path / "vol"
    mount.mkdir()
    nested = mount / "pics" / "b.jpg"
    nested.parent.mkdir()
    nested.write_bytes(b"x")

    stored = stored_path_for_file(nested, mount_point=str(mount))
    assert stored == "pics/b.jpg"
