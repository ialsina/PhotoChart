"""Tests for photochart.fs.storage_probe."""

from unittest.mock import patch

from photochart.fs.storage_probe import (
    StorageProbeResult,
    _lsblk_parent_disk_identity,
    _run_findmnt,
    canonical_filesystem_uuid,
    legacy_filesystem_uuid,
    synthetic_block_filesystem_uuid,
    synthetic_fuse_filesystem_uuid,
    volume_filesystem_uuid,
    probe_storage_from_path,
)


def test_canonical_filesystem_uuid() -> None:
    assert (
        canonical_filesystem_uuid("A1B2C3D4-E5F6-7890-ABCD-EF1234567890")
        == "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    )
    assert canonical_filesystem_uuid("-") is None
    assert canonical_filesystem_uuid("not-a-uuid") is None


def test_legacy_filesystem_uuid_stable() -> None:
    a = legacy_filesystem_uuid("MyDisk (/mnt/x)")
    b = legacy_filesystem_uuid("MyDisk (/mnt/x)")
    assert a == b
    assert a.startswith("photchart:legacy:")


def test_volume_filesystem_uuid_prefers_real_uuid() -> None:
    probe = StorageProbeResult(
        filesystem_uuid="A1B2C3D4-E5F6-7890-ABCD-EF1234567890",
        mount_root="/mnt/x",
        fstype="ext4",
    )
    assert volume_filesystem_uuid(probe, "label") == (
        "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    )


def test_volume_filesystem_uuid_fuse_synthetic() -> None:
    probe = StorageProbeResult(
        mount_root="/home/user/pCloudDrive",
        fstype="fuse.rclone",
        source="pcloudfs",
        notes="fuse_cloud",
    )
    uuid = volume_filesystem_uuid(probe, "pCloudDrive (/home/user/pCloudDrive)")
    assert uuid.startswith("photchart:fuse:")
    assert uuid == synthetic_fuse_filesystem_uuid(
        "/home/user/pCloudDrive", "fuse.rclone", "pcloudfs"
    )


def test_volume_filesystem_uuid_block_not_legacy() -> None:
    probe = StorageProbeResult(
        source="/dev/sdb1",
        fstype="vfat",
        mount_root="/media/usb",
    )
    uuid = volume_filesystem_uuid(probe, "USB (/media/usb)")
    assert uuid.startswith("photchart:block:")
    assert not uuid.startswith("photchart:legacy:")
    assert uuid == synthetic_block_filesystem_uuid("/dev/sdb1")


def test_probe_fills_uuid_from_blkid_when_findmnt_empty() -> None:
    with (
        patch(
            "photochart.fs.storage_probe._run_findmnt",
            return_value={
                "uuid": "-",
                "source": "/dev/sda1",
                "fstype": "ext4",
                "target": "/mnt/data",
            },
        ),
        patch(
            "photochart.fs.storage_probe._blkid_filesystem_uuid",
            return_value="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        ),
        patch(
            "photochart.fs.storage_probe.get_mount_point_from_file",
            return_value=None,
        ),
        patch(
            "photochart.fs.storage_probe._statvfs_capacity_bytes",
            return_value=None,
        ),
    ):
        result = probe_storage_from_path("/mnt/data/file.jpg", deep=False)
    assert result.filesystem_uuid == "a1b2c3d4-e5f6-7890-abcd-ef1234567890"


def test_run_findmnt_without_uuid_column(monkeypatch) -> None:
    def fake_run(cmd, **kwargs):
        assert cmd[0] == "findmnt"
        from subprocess import CompletedProcess

        return CompletedProcess(
            args=cmd,
            returncode=0,
            stdout=" /dev/nvme0n1p6 ext4 / 181018693632\n",
            stderr="",
        )

    monkeypatch.setattr("photochart.fs.storage_probe.subprocess.run", fake_run)
    assert _run_findmnt("/") == {
        "uuid": "-",
        "source": "/dev/nvme0n1p6",
        "fstype": "ext4",
        "target": "/",
        "size": "181018693632",
    }


def test_lsblk_parent_disk_identity_stops_when_pkname_is_self(monkeypatch) -> None:
    calls = {"n": 0}

    def fake_run(cmd, **kwargs):
        from subprocess import CompletedProcess

        calls["n"] += 1
        if any("PKNAME" in part for part in cmd):
            return CompletedProcess(
                args=cmd, returncode=0, stdout="nvme0n1\n", stderr=""
            )
        if any("MODEL" in part for part in cmd):
            return CompletedProcess(
                args=cmd, returncode=0, stdout="MyModel SN123 VendorX\n", stderr=""
            )
        return CompletedProcess(args=cmd, returncode=1, stdout="", stderr="")

    monkeypatch.setattr("photochart.fs.storage_probe.subprocess.run", fake_run)
    fields = _lsblk_parent_disk_identity("/dev/nvme0n1p6")
    assert fields.get("model") == "MyModel"
    assert fields.get("serial") == "SN123"
    assert fields.get("vendor") == "VendorX"
    assert calls["n"] < 20


def test_probe_serial_from_parent_disk() -> None:
    with (
        patch(
            "photochart.fs.storage_probe._run_findmnt",
            return_value={
                "uuid": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "source": "/dev/sda1",
                "fstype": "ext4",
                "target": "/mnt/data",
            },
        ),
        patch(
            "photochart.fs.storage_probe._lsblk_parent_disk_identity",
            return_value={"serial": "ABC123", "vendor": "SanDisk", "model": "Extreme"},
        ),
        patch(
            "photochart.fs.storage_probe.get_mount_point_from_file",
            return_value=None,
        ),
        patch(
            "photochart.fs.storage_probe._statvfs_capacity_bytes",
            return_value=None,
        ),
    ):
        result = probe_storage_from_path("/mnt/data", deep=True)
    assert result.serial == "ABC123"
    assert result.vendor == "SanDisk"
    assert result.model == "Extreme"
