import importlib
from pathlib import Path

import pytest

from photochart.fs.storage_probe import StorageProbeResult


def test_non_database_command_does_not_initialize_django(monkeypatch) -> None:
    cli_main = importlib.import_module("cli.main")

    def fail() -> None:
        raise AssertionError("Django should not be initialized")

    monkeypatch.setattr(cli_main, "_setup_django", fail)

    assert cli_main.main(["list-resolutions"]) == 0


def test_resize_thumbnails_initializes_django(monkeypatch) -> None:
    cli_main = importlib.import_module("cli.main")

    called = {"value": False}

    def mark_setup() -> None:
        called["value"] = True

    monkeypatch.setattr(cli_main, "_setup_django", mark_setup)
    monkeypatch.setattr(
        "photochart.catalog.resize_thumbnails.resize_all_thumbnails",
        lambda **kwargs: {
            "success": True,
            "resized": 0,
            "skipped_too_small": 0,
            "skipped_no_thumbnail": 0,
            "failed": 0,
            "errors": [],
        },
    )

    assert cli_main.main(["resize-thumbnails", "--resolution", "medium"]) == 0
    assert called["value"] is True


def test_resize_thumbnails_requires_resolution() -> None:
    cli_main = importlib.import_module("cli.main")
    with pytest.raises(SystemExit):
        cli_main.main(["resize-thumbnails"])


def test_volume_info_does_not_initialize_django(monkeypatch, tmp_path: Path) -> None:
    cli_main = importlib.import_module("cli.main")
    probe_file = tmp_path / "photo.jpg"
    probe_file.write_bytes(b"x")

    def fail() -> None:
        raise AssertionError("Django should not be initialized")

    monkeypatch.setattr(cli_main, "_setup_django", fail)
    monkeypatch.setattr(
        "photochart.fs.storage_probe.probe_storage_from_path",
        lambda path, **kwargs: StorageProbeResult(
            filesystem_uuid="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            capacity_bytes=1_000_000_000,
            vendor="ACME",
            model="USB Stick",
            serial="SN123",
            source="/dev/sdb1",
            fstype="ext4",
            mount_root=str(tmp_path),
        ),
    )

    assert cli_main.main(["volume-info", "--json", str(probe_file)]) == 0


def test_volume_info_missing_path() -> None:
    cli_main = importlib.import_module("cli.main")
    assert cli_main.main(["volume-info", "/no/such/path"]) == 1
