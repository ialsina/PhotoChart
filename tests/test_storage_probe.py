"""Tests for photochart.fs.storage_probe."""

from photochart.fs.storage_probe import (
    StorageProbeResult,
    canonical_filesystem_uuid,
    legacy_filesystem_uuid,
    synthetic_fuse_filesystem_uuid,
    volume_filesystem_uuid,
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
