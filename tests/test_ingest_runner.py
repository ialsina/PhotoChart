"""Tests for photochart.ingest.runner.

Covers path validation, mount-root resolution, device label building,
and the local/docker dispatch logic – all without touching real
filesystems or spawning containers.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from photochart.ingest.runner import (
    build_device_label,
    resolve_mount_root,
    validate_ingest_path,
    run_ingest_docker,
    run_ingest_local,
    choose_and_run_ingest,
)


# ---------------------------------------------------------------------------
# validate_ingest_path
# ---------------------------------------------------------------------------


class TestValidateIngestPath:
    def test_absolute_path_returned_unchanged(self, tmp_path: Path) -> None:
        p = str(tmp_path)
        assert validate_ingest_path(p) == p

    def test_resolves_symlinks_and_relative_parts(self, tmp_path: Path) -> None:
        result = validate_ingest_path(str(tmp_path / "." / "."))
        assert ".." not in result
        assert result == str(tmp_path)

    def test_rejects_dotdot_in_path(self) -> None:
        with pytest.raises(ValueError, match="traversal"):
            validate_ingest_path("/mnt/../etc/passwd")

    def test_rejects_proc(self) -> None:
        with pytest.raises(ValueError, match="restricted"):
            validate_ingest_path("/proc/1/environ")

    def test_rejects_sys(self) -> None:
        with pytest.raises(ValueError, match="restricted"):
            validate_ingest_path("/sys/kernel")

    def test_rejects_root_filesystem(self) -> None:
        with pytest.raises(ValueError, match="root"):
            validate_ingest_path("/")

    def test_rejects_empty_path(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            validate_ingest_path("")

    def test_allowed_prefix_passes(self, tmp_path: Path) -> None:
        inner = tmp_path / "DCIM"
        inner.mkdir()
        result = validate_ingest_path(str(inner), allowed_prefixes=[str(tmp_path)])
        assert result == str(inner)

    def test_disallowed_prefix_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="allowed prefix"):
            validate_ingest_path(str(tmp_path), allowed_prefixes=["/mnt"])


# ---------------------------------------------------------------------------
# resolve_mount_root
# ---------------------------------------------------------------------------


class TestResolveMountRoot:
    def test_returns_findmnt_output_when_available(self, tmp_path: Path) -> None:
        fake_stdout = "/mnt/camera\n"
        with patch(
            "photochart.ingest.runner.subprocess.run",
            return_value=MagicMock(returncode=0, stdout=fake_stdout),
        ):
            result = resolve_mount_root(str(tmp_path))
        assert result == "/mnt/camera"

    def test_falls_back_when_findmnt_not_found(self, tmp_path: Path) -> None:
        with patch(
            "photochart.ingest.runner.subprocess.run",
            side_effect=FileNotFoundError,
        ):
            with patch(
                "photochart.fs.device.get_mount_point",
                return_value="/mnt/sd",
            ):
                result = resolve_mount_root(str(tmp_path))
        assert result == "/mnt/sd"

    def test_falls_back_to_path_when_root_returned(self, tmp_path: Path) -> None:
        """When findmnt says '/', fall back to the path itself."""
        with patch(
            "photochart.ingest.runner.subprocess.run",
            return_value=MagicMock(returncode=0, stdout="/\n"),
        ):
            result = resolve_mount_root(str(tmp_path))
        # Should not return "/" – falls through to /proc/mounts or path fallback
        assert result != "/"


# ---------------------------------------------------------------------------
# build_device_label
# ---------------------------------------------------------------------------


class TestBuildDeviceLabel:
    def test_uses_label_and_target(self, tmp_path: Path) -> None:
        with patch(
            "photochart.ingest.runner.subprocess.run",
            return_value=MagicMock(returncode=0, stdout="MyDisk /mnt/camera\n"),
        ):
            label = build_device_label(str(tmp_path))
        assert label == "MyDisk (/mnt/camera)"

    def test_uses_target_when_label_missing(self, tmp_path: Path) -> None:
        with patch(
            "photochart.ingest.runner.subprocess.run",
            return_value=MagicMock(returncode=0, stdout="- /mnt/camera\n"),
        ):
            label = build_device_label(str(tmp_path))
        assert label == "/mnt/camera"

    def test_falls_back_to_get_device_name(self, tmp_path: Path) -> None:
        with patch(
            "photochart.ingest.runner.subprocess.run",
            side_effect=FileNotFoundError,
        ):
            with patch(
                "photochart.fs.device.get_device_name",
                return_value="fallback-device",
            ):
                label = build_device_label(str(tmp_path))
        assert label == "fallback-device"


# ---------------------------------------------------------------------------
# run_ingest_docker
# ---------------------------------------------------------------------------


class TestRunIngestDocker:
    _GOOD_STDOUT = (
        "Ingesting photos: 100%|████████████| 3/3 [00:00<00:00,  5.12file/s]\n"
        "Ingested 3 photo(s) from '/mnt/camera/DCIM'.\n"
        "Calculated 3 checksum(s).\n"
        "Stored 3 image(s) in database.\n"
    )

    def _patched_settings(
        self,
        compose_file="/app/docker/compose.yaml",
        project="photochart",
        compose_files="",
    ):
        """Return a context manager that patches django.conf.settings attributes."""
        import django.conf

        class _FakeSettings:
            INGEST_COMPOSE_FILE = compose_file
            COMPOSE_FILE = compose_files
            COMPOSE_PROJECT_NAME = project

        return patch.object(django.conf, "settings", _FakeSettings())

    def test_success_parses_stdout(self) -> None:
        with self._patched_settings():
            with patch(
                "photochart.ingest.runner.subprocess.run",
                return_value=MagicMock(
                    returncode=0, stdout=self._GOOD_STDOUT, stderr=""
                ),
            ) as mock_run:
                result = run_ingest_docker(
                    path="/mnt/camera/DCIM",
                    mount_root="/mnt/camera",
                    device="MyDisk (/mnt/camera)",
                )

        assert result["success"] is True
        assert result["count"] == 3
        assert result["checksums_calculated"] == 3
        assert result["images_stored"] == 3
        assert result["errors"] == []

        cmd = mock_run.call_args[0][0]
        assert "-v" in cmd
        assert "/mnt/camera:/mnt/camera:ro" in cmd
        assert "--device" in cmd
        assert "MyDisk (/mnt/camera)" in cmd

    def test_nonzero_exit_returns_failure(self) -> None:
        with self._patched_settings():
            with patch(
                "photochart.ingest.runner.subprocess.run",
                return_value=MagicMock(returncode=1, stdout="", stderr="some error"),
            ):
                result = run_ingest_docker(
                    path="/mnt/camera/DCIM", mount_root="/mnt/camera"
                )
        assert result["success"] is False
        assert result["errors"]

    def test_timeout_returns_failure(self) -> None:
        with self._patched_settings():
            with patch(
                "photochart.ingest.runner.subprocess.run",
                side_effect=subprocess.TimeoutExpired(cmd=[], timeout=1),
            ):
                result = run_ingest_docker(
                    path="/mnt/camera/DCIM", mount_root="/mnt/camera", timeout=1
                )
        assert result["success"] is False
        assert "timed out" in result["errors"][0]

    def test_docker_not_found_returns_failure(self) -> None:
        with self._patched_settings():
            with patch(
                "photochart.ingest.runner.subprocess.run",
                side_effect=FileNotFoundError,
            ):
                result = run_ingest_docker(
                    path="/mnt/camera/DCIM", mount_root="/mnt/camera"
                )
        assert result["success"] is False
        assert "docker" in result["errors"][0].lower()

    def test_no_device_flag_when_device_is_none(self) -> None:
        with self._patched_settings():
            with patch(
                "photochart.ingest.runner.subprocess.run",
                return_value=MagicMock(
                    returncode=0, stdout="Ingested 0 photo(s) from '/x'.", stderr=""
                ),
            ) as mock_run:
                run_ingest_docker(path="/x", mount_root="/x", device=None)

        cmd = mock_run.call_args[0][0]
        assert "--device" not in cmd

    def test_retry_thumbnails_flag_forwarded(self) -> None:
        with self._patched_settings():
            with patch(
                "photochart.ingest.runner.subprocess.run",
                return_value=MagicMock(
                    returncode=0,
                    stdout="Ingested 0 photo(s) from '/x'.",
                    stderr="",
                ),
            ) as mock_run:
                run_ingest_docker(path="/x", mount_root="/x", retry_thumbnails=True)

        cmd = mock_run.call_args[0][0]
        assert "--retry-thumbnails" in cmd

    def test_no_recursive_flag_forwarded(self) -> None:
        with self._patched_settings():
            with patch(
                "photochart.ingest.runner.subprocess.run",
                return_value=MagicMock(
                    returncode=0, stdout="Ingested 0 photo(s) from '/x'.", stderr=""
                ),
            ) as mock_run:
                run_ingest_docker(path="/x", mount_root="/x", recursive=False)

        cmd = mock_run.call_args[0][0]
        assert "--no-recursive" in cmd

    def test_compose_file_list_expands_to_multiple_file_flags(self) -> None:
        with self._patched_settings(
            compose_files="/app/docker/compose.yaml:/app/docker/compose.host-postgres.yaml"
        ):
            with patch(
                "photochart.ingest.runner.subprocess.run",
                return_value=MagicMock(
                    returncode=0, stdout="Ingested 0 photo(s) from '/x'.", stderr=""
                ),
            ) as mock_run:
                run_ingest_docker(path="/x", mount_root="/x")

        cmd = mock_run.call_args[0][0]
        assert cmd[:8] == [
            "docker",
            "compose",
            "--project-directory",
            "/app",
            "-f",
            "/app/docker/compose.yaml",
            "-f",
            "/app/docker/compose.host-postgres.yaml",
        ]


# ---------------------------------------------------------------------------
# choose_and_run_ingest
# ---------------------------------------------------------------------------


def _fake_django_settings(**kwargs):
    """Build a patch context on django.conf.settings with given attributes."""
    import django.conf

    defaults = dict(
        INGEST_DOCKER_ENABLED=False,
        INGEST_ALLOWED_PATH_PREFIXES="",
        INGEST_COMPOSE_FILE="/app/docker/compose.yaml",
        COMPOSE_FILE="",
        COMPOSE_PROJECT_NAME="photochart",
    )
    defaults.update(kwargs)

    class _S:
        pass

    for k, v in defaults.items():
        setattr(_S, k, v)

    return patch.object(django.conf, "settings", _S())


class TestChooseAndRunIngest:
    def test_local_path_takes_local_branch(self, tmp_path: Path) -> None:
        mock_result = {
            "success": True,
            "count": 2,
            "checksums_calculated": 2,
            "images_stored": 2,
            "errors": [],
        }
        with _fake_django_settings():
            with patch(
                "photochart.ingest.runner.run_ingest_local", return_value=mock_result
            ) as mock_local:
                result = choose_and_run_ingest(str(tmp_path))

        mock_local.assert_called_once()
        assert result["success"] is True

    def test_retry_thumbnails_forwarded_to_local(self, tmp_path: Path) -> None:
        mock_result = {
            "success": True,
            "count": 0,
            "checksums_calculated": 0,
            "images_stored": 1,
            "thumbnails_retried": 1,
            "errors": [],
        }
        with _fake_django_settings():
            with patch(
                "photochart.ingest.runner.run_ingest_local", return_value=mock_result
            ) as mock_local:
                choose_and_run_ingest(
                    str(tmp_path), retry_thumbnails=True, store_images=False
                )

        call_kwargs = mock_local.call_args.kwargs
        assert call_kwargs["retry_thumbnails"] is True
        assert call_kwargs["store_images"] is True

    def test_missing_path_without_docker_returns_error(self) -> None:
        with _fake_django_settings(INGEST_DOCKER_ENABLED=False):
            result = choose_and_run_ingest("/nonexistent/path/that/doesnt/exist")

        assert result["success"] is False
        assert "INGEST_DOCKER_ENABLED" in result["errors"][0]

    def test_missing_path_with_docker_but_no_prefix_returns_error(self) -> None:
        with _fake_django_settings(
            INGEST_DOCKER_ENABLED=True, INGEST_ALLOWED_PATH_PREFIXES=""
        ):
            result = choose_and_run_ingest("/nonexistent/path")

        assert result["success"] is False
        assert "INGEST_ALLOWED_PATH_PREFIXES" in result["errors"][0]

    def test_missing_path_with_docker_and_prefix_calls_docker(self) -> None:
        mock_result = {
            "success": True,
            "count": 5,
            "checksums_calculated": 5,
            "images_stored": 5,
            "errors": [],
        }
        with _fake_django_settings(
            INGEST_DOCKER_ENABLED=True,
            INGEST_ALLOWED_PATH_PREFIXES="/mnt",
        ):
            with patch(
                "photochart.ingest.runner.run_ingest_docker", return_value=mock_result
            ) as mock_docker:
                with patch(
                    "photochart.ingest.runner.resolve_mount_root", return_value="/mnt"
                ):
                    result = choose_and_run_ingest(
                        "/mnt/camera/DCIM", device="MyDisk (/mnt/camera)"
                    )

        mock_docker.assert_called_once()
        assert result["success"] is True

    def test_dangerous_path_rejected_before_local_check(self) -> None:
        with _fake_django_settings():
            result = choose_and_run_ingest("/proc/1/fd")

        assert result["success"] is False
        assert "restricted" in result["errors"][0]
