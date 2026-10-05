"""Tests for mount table helpers in photochart.fs.device."""

from photochart.fs.device import load_mount_table, mount_point_for_path


def test_mount_point_for_path_longest_prefix_wins() -> None:
    table = ["/mnt/camera", "/mnt/camera/DCIM", "/mnt/other"]
    table.sort(key=len, reverse=True)
    assert mount_point_for_path("/mnt/camera/DCIM/IMG_001.jpg", table) == (
        "/mnt/camera/DCIM"
    )


def test_mount_point_for_path_exact_mount() -> None:
    table = ["/mnt/camera"]
    assert mount_point_for_path("/mnt/camera", table) == "/mnt/camera"


def test_mount_point_for_path_no_match() -> None:
    table = ["/mnt/camera"]
    assert mount_point_for_path("/var/log/syslog", table) is None


def test_load_mount_table_reads_proc_mounts(monkeypatch, tmp_path) -> None:
    mounts_file = tmp_path / "mounts"
    mounts_file.write_text(
        "/dev/sda1 / ext4 rw 0 0\n" "/dev/sdb1 /mnt/camera ext4 rw 0 0\n",
        encoding="utf-8",
    )
    table = load_mount_table(str(mounts_file))
    assert "/mnt/camera" in table
    assert "/" not in table
