from pathlib import Path

import pytest

from photochart.organizer.adapters.pcloud_drive import PCloudDriveAdapter
from photochart.organizer.domain import OrganizerError


def test_pcloud_drive_restricts_paths_to_mount(tmp_path: Path) -> None:
    mount = tmp_path / "pCloud"
    mount.mkdir()
    adapter = PCloudDriveAdapter(str(mount))

    adapter.healthcheck()
    adapter.ensure_directory(str(mount / "Photos"))

    assert (mount / "Photos").is_dir()
    assert not adapter.get_capabilities().atomic_move


def test_pcloud_drive_rejects_outside_path(tmp_path: Path) -> None:
    mount = tmp_path / "pCloud"
    mount.mkdir()
    adapter = PCloudDriveAdapter(str(mount))

    with pytest.raises(OrganizerError):
        adapter.exists(str(tmp_path / "outside.jpg"))
