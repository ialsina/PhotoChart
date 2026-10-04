"""Tests for photochart.fs.mounts.

Covers path validation, mount-root resolution, mount-root collection, and
Docker bind-flag generation – all without touching real filesystems or
spawning containers.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from photochart.fs.mounts import (
    DEFAULT_ALWAYS_ALLOWED,
    DANGEROUS_PREFIXES,
    validate_host_path,
    resolve_mount_root,
    collect_mount_roots,
    docker_bind_flags,
)


# ---------------------------------------------------------------------------
# validate_host_path
# ---------------------------------------------------------------------------


class TestValidateHostPath:
    def test_absolute_path_returned_resolved(self, tmp_path: Path) -> None:
        p = str(tmp_path)
        assert validate_host_path(p) == p

    def test_resolves_trailing_dot(self, tmp_path: Path) -> None:
        result = validate_host_path(str(tmp_path / "." / "."))
        assert ".." not in result
        assert result == str(tmp_path)

    def test_rejects_empty_string(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            validate_host_path("")

    def test_rejects_whitespace_only(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            validate_host_path("   ")

    def test_rejects_dotdot_in_path(self) -> None:
        with pytest.raises(ValueError, match="traversal"):
            validate_host_path("/mnt/../etc/passwd")

    def test_rejects_proc(self) -> None:
        with pytest.raises(ValueError, match="restricted"):
            validate_host_path("/proc/1/environ")

    def test_rejects_sys(self) -> None:
        with pytest.raises(ValueError, match="restricted"):
            validate_host_path("/sys/class")

    def test_rejects_dev(self) -> None:
        with pytest.raises(ValueError, match="restricted"):
            validate_host_path("/dev/sda")

    def test_rejects_docker_sock(self) -> None:
        with pytest.raises(ValueError, match="restricted"):
            validate_host_path("/var/run/docker.sock")

    def test_rejects_filesystem_root(self) -> None:
        with pytest.raises(ValueError, match="root"):
            validate_host_path("/")

    def test_allowed_prefix_passes(self, tmp_path: Path) -> None:
        result = validate_host_path(str(tmp_path), allowed_prefixes=[str(tmp_path)])
        assert result == str(tmp_path)

    def test_outside_allowed_prefix_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="not under any allowed prefix"):
            validate_host_path(str(tmp_path), allowed_prefixes=["/mnt"])

    def test_always_allowed_bypasses_prefix_check(self, tmp_path: Path) -> None:
        # Even though allowed_prefixes is set to /mnt, always_allowed lets /tmp through
        result = validate_host_path(
            str(tmp_path),
            allowed_prefixes=["/mnt"],
            always_allowed=[str(tmp_path.parent)],
        )
        assert result == str(tmp_path)

    def test_default_always_allowed_includes_photos(self) -> None:
        assert "/photos" in DEFAULT_ALWAYS_ALLOWED

    def test_no_prefix_check_when_allowed_prefixes_empty(self, tmp_path: Path) -> None:
        # Empty list → no check at all
        result = validate_host_path(str(tmp_path), allowed_prefixes=[])
        assert result == str(tmp_path)

    def test_no_prefix_check_when_allowed_prefixes_none(self, tmp_path: Path) -> None:
        result = validate_host_path(str(tmp_path), allowed_prefixes=None)
        assert result == str(tmp_path)

    def test_dangerous_prefix_in_allowed_still_rejected(self) -> None:
        # Even if /proc is in allowed_prefixes, it must still be blocked
        with pytest.raises(ValueError, match="restricted"):
            validate_host_path("/proc/mounts", allowed_prefixes=["/proc"])


# ---------------------------------------------------------------------------
# resolve_mount_root
# ---------------------------------------------------------------------------


class TestResolveMountRoot:
    def _make_findmnt_result(self, stdout: str, returncode: int = 0) -> MagicMock:
        m = MagicMock()
        m.returncode = returncode
        m.stdout = stdout
        return m

    def test_returns_findmnt_target_when_available(self, tmp_path: Path) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = self._make_findmnt_result("/mnt/camera\n")
            result = resolve_mount_root(str(tmp_path))
        assert result == "/mnt/camera"

    def test_skips_root_mount_from_findmnt(self, tmp_path: Path) -> None:
        """When findmnt returns '/' it is not a useful bind root; fall through."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = self._make_findmnt_result("/\n")
            with patch("photochart.fs.mounts.resolve_mount_root") as _:
                # Trigger the real fallback by calling the original
                pass
        # Simpler: just check it never returns "/"
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = self._make_findmnt_result("/\n")
            with patch(
                "photochart.fs.device.get_mount_point", return_value=None, create=True
            ):
                result = resolve_mount_root(str(tmp_path))
        assert result != "/"

    def test_fallback_when_findmnt_not_found(self, tmp_path: Path) -> None:
        with patch("subprocess.run", side_effect=FileNotFoundError):
            with patch(
                "photochart.fs.device.get_mount_point",
                return_value="/mnt/sd",
                create=True,
            ):
                result = resolve_mount_root(str(tmp_path))
        assert result == "/mnt/sd"

    def test_fallback_to_path_dir_when_all_else_fails(self, tmp_path: Path) -> None:
        a_file = tmp_path / "photo.jpg"
        a_file.write_text("x")
        with patch("subprocess.run", side_effect=FileNotFoundError):
            with patch(
                "photochart.fs.device.get_mount_point", return_value=None, create=True
            ):
                result = resolve_mount_root(str(a_file))
        # Falls back to the parent directory of the file
        assert result == str(tmp_path)

    def test_fallback_to_path_itself_for_directory(self, tmp_path: Path) -> None:
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 5)):
            with patch(
                "photochart.fs.device.get_mount_point", return_value=None, create=True
            ):
                result = resolve_mount_root(str(tmp_path))
        assert result == str(tmp_path)


# ---------------------------------------------------------------------------
# collect_mount_roots
# ---------------------------------------------------------------------------


class TestCollectMountRoots:
    def _mock_resolve(self, path_to_root: dict) -> MagicMock:
        """Return a side_effect that maps paths to mock mount roots."""

        def _side_effect(p):
            # Match longest prefix
            for k, v in sorted(path_to_root.items(), key=lambda x: -len(x[0])):
                if p == k or p.startswith(k.rstrip("/") + "/"):
                    return v
            return p

        return _side_effect

    def test_returns_unique_roots(self, tmp_path: Path) -> None:
        d1 = str(tmp_path / "a" / "DCIM")
        d2 = str(tmp_path / "a" / "other")
        (tmp_path / "a").mkdir()

        with patch(
            "photochart.fs.mounts.resolve_mount_root",
            return_value=str(tmp_path / "a"),
        ):
            result = collect_mount_roots([d1, d2])
        assert result == [str(tmp_path / "a")]

    def test_skips_library_paths(self, tmp_path: Path) -> None:
        """Paths under /photos must be excluded (already mounted)."""
        with patch(
            "photochart.fs.mounts.resolve_mount_root",
            return_value="/mnt/cam",
        ) as mock_resolve:
            result = collect_mount_roots(["/photos/Photos", "/mnt/cam/DCIM"])
        # /photos/Photos is skipped; /mnt/cam/DCIM is kept
        assert result == ["/mnt/cam"]
        # resolve_mount_root should only have been called for the non-library path
        mock_resolve.assert_called_once()

    def test_custom_skip_prefix(self, tmp_path: Path) -> None:
        with patch(
            "photochart.fs.mounts.resolve_mount_root",
            return_value=str(tmp_path),
        ) as mock_resolve:
            # skip_prefixes overrides default
            result = collect_mount_roots(
                [str(tmp_path / "sub")],
                skip_prefixes=[str(tmp_path)],
            )
        assert result == []
        mock_resolve.assert_not_called()

    def test_empty_paths(self) -> None:
        result = collect_mount_roots(["", "  ", ""])
        assert result == []

    def test_two_different_roots(self, tmp_path: Path) -> None:
        d1 = str(tmp_path / "disk1" / "DCIM")
        d2 = str(tmp_path / "disk2" / "Photos")
        (tmp_path / "disk1").mkdir()
        (tmp_path / "disk2").mkdir()

        def _resolve(p):
            if "disk1" in p:
                return str(tmp_path / "disk1")
            return str(tmp_path / "disk2")

        with patch("photochart.fs.mounts.resolve_mount_root", side_effect=_resolve):
            result = collect_mount_roots([d1, d2])
        assert len(result) == 2
        assert str(tmp_path / "disk1") in result
        assert str(tmp_path / "disk2") in result


# ---------------------------------------------------------------------------
# docker_bind_flags
# ---------------------------------------------------------------------------


class TestDockerBindFlags:
    def test_single_ro_flag(self) -> None:
        flags = docker_bind_flags(["/mnt/camera"])
        assert flags == ["-v", "/mnt/camera:/mnt/camera:ro"]

    def test_single_rw_flag(self) -> None:
        flags = docker_bind_flags(["/mnt/camera"], mode="rw")
        assert flags == ["-v", "/mnt/camera:/mnt/camera:rw"]

    def test_multiple_roots(self) -> None:
        flags = docker_bind_flags(["/mnt/a", "/mnt/b"])
        assert flags == ["-v", "/mnt/a:/mnt/a:ro", "-v", "/mnt/b:/mnt/b:ro"]

    def test_empty_list(self) -> None:
        assert docker_bind_flags([]) == []

    def test_invalid_mode_raises(self) -> None:
        with pytest.raises(ValueError, match="mode must be"):
            docker_bind_flags(["/mnt/x"], mode="invalid")

    def test_trailing_slash_stripped(self) -> None:
        flags = docker_bind_flags(["/mnt/camera/"])
        assert flags == ["-v", "/mnt/camera:/mnt/camera:ro"]

    def test_root_stripped_to_slash(self) -> None:
        # "/" stripped of "/" is "", then "" or "/" → kept as "/"
        flags = docker_bind_flags(["/"])
        assert flags[1].startswith("/:/:")


# ---------------------------------------------------------------------------
# validate_ingest_path backward-compat shim (runner module)
# ---------------------------------------------------------------------------


class TestValidateIngestPathShim:
    """validate_ingest_path in runner.py must remain usable for existing callers."""

    def test_shim_delegates_to_validate_host_path(self, tmp_path: Path) -> None:
        from photochart.ingest.runner import validate_ingest_path

        result = validate_ingest_path(str(tmp_path))
        assert result == str(tmp_path)

    def test_shim_always_allowed_passed_through(self, tmp_path: Path) -> None:
        from photochart.ingest.runner import validate_ingest_path

        result = validate_ingest_path(
            str(tmp_path),
            allowed_prefixes=["/mnt"],
            always_allowed=[str(tmp_path.parent)],
        )
        assert result == str(tmp_path)

    def test_shim_rejects_dangerous_path(self) -> None:
        from photochart.ingest.runner import validate_ingest_path

        with pytest.raises(ValueError, match="restricted"):
            validate_ingest_path("/proc/1")
