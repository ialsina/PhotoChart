"""Ingest orchestration: validate paths, resolve mount roots, run local or via Docker.

This module bridges the gap when a host path (USB drive, SD card, another
directory not in the default library bind-mount) needs to be ingested into a
catalog running inside Docker Compose.  It provides three entry points:

* ``validate_ingest_path`` - normalise and security-check a raw path string.
* ``resolve_mount_root``   - find the filesystem root for any path (Linux only).
* ``build_device_label``   - produce a stable device label mirroring
                             ``photochart.fs.device.get_device_name``.
* ``run_ingest_local``     - call ``ingest_photos`` directly when the path is
                             already visible in the current process namespace.
* ``run_ingest_docker``    - launch a one-shot ``docker compose run`` container
                             that bind-mounts only the given mount root, so the
                             long-running ``web``/``worker`` services are not
                             restarted.
* ``choose_and_run_ingest``- dispatch to local or Docker based on path
                             visibility and ``INGEST_DOCKER_ENABLED``.

All functions return a result dict compatible with ``photochart.ingest.photos.ingest_photos``:
    ``{"success": bool, "count": int, "checksums_calculated": int,
       "images_stored": int, "errors": list[str]}``
"""

from __future__ import annotations

import os
import re
import subprocess
import logging
from pathlib import Path
from typing import Optional

from photochart.fs.mounts import (
    validate_host_path,
    resolve_mount_root,
    collect_mount_roots,  # noqa: F401 – re-exported for callers that import from here
    docker_bind_flags,  # noqa: F401
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Path validation (thin wrapper kept for backward compatibility)
# ---------------------------------------------------------------------------


def validate_ingest_path(
    path: str,
    allowed_prefixes: Optional[list[str]] = None,
    always_allowed: Optional[list[str]] = None,
) -> str:
    """Return the normalised absolute path or raise ``ValueError``.

    Delegates to :func:`photochart.fs.mounts.validate_host_path`.  The
    *always_allowed* argument controls which prefixes bypass the
    *allowed_prefixes* check (defaults to ``["/photos"]``).

    Args:
        path:             Raw path supplied by the caller.
        allowed_prefixes: If non-empty, the resolved path must start with
                          at least one of these *or* one of *always_allowed*.
        always_allowed:   Prefixes that are always valid (default ``["/photos"]``).

    Returns:
        Resolved absolute path string.

    Raises:
        ValueError: Path is invalid, dangerous, or outside allowed prefixes.
    """
    return validate_host_path(
        path,
        allowed_prefixes=allowed_prefixes,
        always_allowed=always_allowed,
    )


# ---------------------------------------------------------------------------
# Device label
# ---------------------------------------------------------------------------


def build_device_label(path: str) -> str:
    """Return a stable device label for *path* suitable for ``PhotoPath.device``.

    Mirrors the format produced by ``photochart.fs.device.get_device_name``
    (``"LABEL (/mnt/target)"``).  If ``findmnt`` is unavailable, falls back
    to ``get_device_name``.

    Args:
        path: Absolute path to a file or directory on the device.

    Returns:
        Device label string.
    """
    try:
        result = subprocess.run(
            [
                "findmnt",
                "-T",
                path,
                "--output",
                "LABEL,TARGET",
                "--noheadings",
                "--raw",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            line = result.stdout.strip()
            if line:
                parts = line.split(None, 1)
                if len(parts) == 2:
                    label, target = parts[0].strip(), parts[1].strip()
                    if label and label not in ("-", ""):
                        return f"{label} ({target})"
                    if target and target != "/":
                        return target
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    # Fall back to existing device detection
    try:
        from photochart.fs.device import get_device_name

        return get_device_name(path)
    except Exception:
        return "unknown"


# ---------------------------------------------------------------------------
# Local ingest (path already visible in current namespace)
# ---------------------------------------------------------------------------


def run_ingest_local(
    path: str,
    *,
    device: Optional[str] = None,
    recursive: bool = True,
    calculate_checksum: bool = True,
    store_images: bool = True,
    resolution: Optional[str] = None,
    log_path: Optional[str] = None,
    retry_thumbnails: bool = False,
) -> dict:
    """Call ``ingest_photos`` directly in the current process.

    Use this when *path* is already accessible (e.g. the default
    ``/photos`` library, or during host-side ``pchart ingest`` runs).

    Returns:
        Result dict from ``ingest_photos``.
    """
    from photochart.ingest.photos import ingest_photos

    if retry_thumbnails:
        store_images = True

    return ingest_photos(
        path=path,
        device=device,
        recursive=recursive,
        calculate_checksum=calculate_checksum,
        store_images=store_images,
        resolution=resolution,
        log_path=log_path,
        retry_thumbnails=retry_thumbnails,
    )


# ---------------------------------------------------------------------------
# Docker ingest (path not yet visible inside the container)
# ---------------------------------------------------------------------------


def run_ingest_docker(
    path: str,
    mount_root: str,
    *,
    device: Optional[str] = None,
    recursive: bool = True,
    calculate_checksum: bool = True,
    store_images: bool = True,
    resolution: Optional[str] = None,
    compose_file: Optional[str] = None,
    project_name: Optional[str] = None,
    timeout: int = 3600,
    retry_thumbnails: bool = False,
) -> dict:
    """Spawn a one-shot ``docker compose run`` container that bind-mounts
    *mount_root* read-only, then runs ``pchart ingest`` inside it.

    The one-shot container reuses the ``web`` service definition from
    ``compose.yaml``, so it automatically inherits ``DATABASE_URL``,
    ``MEDIA_ROOT``, the ``media`` named volume, and all other settings.
    Only *mount_root* (the external device's filesystem root) is added
    as an extra read-only bind-mount.

    The ``worker`` container must have ``/var/run/docker.sock`` mounted and
    ``INGEST_DOCKER_ENABLED=true`` set in ``.env`` / ``compose.override.yaml``
    for this function to be reachable.

    Args:
        path:          Absolute path inside the container after bind-mounting.
        mount_root:    The host mount root to bind into the container at the
                       same absolute path (read-only).
        device:        Device label to record in ``PhotoPath.device``.
        recursive:     Pass ``--no-recursive`` when False.
        calculate_checksum: Pass ``--no-checksum`` when False.
        store_images:  Pass ``--no-store-images`` when False.
        resolution:    Optional ``--resolution`` value.
        compose_file:  Path to ``compose.yaml`` inside the container.
                       Defaults to ``settings.INGEST_COMPOSE_FILE``.
        project_name:  Docker Compose project name.
                       Defaults to ``settings.COMPOSE_PROJECT_NAME``.
        timeout:       Subprocess timeout in seconds (default 3600).

    Returns:
        Result dict with ``success``, ``count``, ``checksums_calculated``,
        ``images_stored``, ``errors``.
    """
    from django.conf import settings as django_settings

    compose_file = (
        compose_file
        or getattr(django_settings, "COMPOSE_FILE", "")
        or getattr(django_settings, "INGEST_COMPOSE_FILE", "/app/docker/compose.yaml")
    )
    project_name = project_name or getattr(django_settings, "COMPOSE_PROJECT_NAME", "")

    # Build the docker compose command
    cmd: list[str] = ["docker", "compose", "--project-directory", "/app"]
    for file_name in compose_file.split(os.pathsep):
        if file_name:
            cmd += ["-f", file_name]
    if project_name:
        cmd += ["-p", project_name]
    cmd += [
        "run",
        "--rm",
        "--no-deps",
        "-v",
        f"{mount_root}:{mount_root}:ro",
        "web",
        "pchart",
        "ingest",
        path,
    ]

    if device:
        cmd += ["--device", device]
    if not recursive:
        cmd += ["--no-recursive"]
    if not calculate_checksum:
        cmd += ["--no-checksum"]
    if not store_images:
        cmd += ["--no-store-images"]
    if resolution:
        cmd += ["--resolution", resolution]
    if retry_thumbnails:
        cmd += ["--retry-thumbnails"]

    logger.info(
        "Launching one-shot ingest container: %s",
        " ".join(cmd),
    )

    result: dict = {
        "success": False,
        "count": 0,
        "checksums_calculated": 0,
        "images_stored": 0,
        "thumbnails_retried": 0,
        "skipped_already_ingested": 0,
        "errors": [],
    }

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        result["errors"].append(f"Ingest container timed out after {timeout}s: {exc}")
        logger.error("Ingest container timed out: %s", exc)
        return result
    except FileNotFoundError:
        result["errors"].append(
            "docker command not found. Ensure docker is installed and the "
            "worker container has /var/run/docker.sock mounted."
        )
        return result
    except Exception as exc:
        result["errors"].append(f"Failed to launch ingest container: {exc}")
        logger.exception("Unexpected error launching ingest container")
        return result

    if proc.returncode != 0:
        stderr = proc.stderr.strip()
        result["errors"].append(
            f"Ingest container exited with code {proc.returncode}. stderr: {stderr}"
        )
        logger.error(
            "Ingest container failed (exit=%d): %s",
            proc.returncode,
            stderr,
        )
        return result

    # Parse stdout from pchart ingest:
    # "Ingested 42 photo(s) from '/mnt/camera/DCIM'."
    # "Calculated 42 checksum(s)."
    # "Stored 42 image(s) in database."
    stdout = proc.stdout or ""
    m = re.search(r"Ingested\s+(\d+)\s+photo", stdout)
    if m:
        result["count"] = int(m.group(1))

    m = re.search(r"Calculated\s+(\d+)\s+checksum", stdout)
    if m:
        result["checksums_calculated"] = int(m.group(1))

    m = re.search(r"Stored\s+(\d+)\s+image", stdout)
    if m:
        result["images_stored"] = int(m.group(1))

    result["success"] = True
    logger.info(
        "Ingest container completed: count=%d, checksums=%d, images=%d",
        result["count"],
        result["checksums_calculated"],
        result["images_stored"],
    )
    return result


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


def choose_and_run_ingest(
    path: str,
    mount_root: Optional[str] = None,
    *,
    device: Optional[str] = None,
    recursive: bool = True,
    calculate_checksum: bool = True,
    store_images: bool = True,
    resolution: Optional[str] = None,
    log_path: Optional[str] = None,
    retry_thumbnails: bool = False,
) -> dict:
    """Dispatch an ingest request to the local or Docker backend.

    Decision logic:

    1. If *path* exists in the current process namespace → ``run_ingest_local``.
    2. Else if ``INGEST_DOCKER_ENABLED`` is ``True`` in settings and
       ``INGEST_ALLOWED_PATH_PREFIXES`` is configured → ``run_ingest_docker``.
    3. Otherwise return a failure result with an actionable error message.

    Args:
        path:           Absolute path to ingest.
        mount_root:     Mount root for the Docker bind-mount.  If *None*,
                        resolved automatically via ``resolve_mount_root``.
        device:         Override device label; auto-detected when *None*.
        recursive:      Pass ``--no-recursive`` when False.
        calculate_checksum: Pass ``--no-checksum`` when False.
        store_images:   Pass ``--no-store-images`` when False.
        resolution:     Optional resolution preset or WxH string.
        log_path:       Path to log file (local branch only).

    Returns:
        Result dict with ``success``, ``count``, ``checksums_calculated``,
        ``images_stored``, ``errors``.
    """
    from django.conf import settings as django_settings

    if retry_thumbnails:
        store_images = True

    # ----- Validate -------------------------------------------------------
    allowed_prefixes: list[str] = [
        p.strip()
        for p in getattr(django_settings, "INGEST_ALLOWED_PATH_PREFIXES", "").split(",")
        if p.strip()
    ]

    # Paths under INGEST_ALWAYS_ALLOWED_PREFIXES (default: /photos) bypass the
    # INGEST_ALLOWED_PATH_PREFIXES check so the library volume is always reachable
    # even when external-device prefixes are also configured.
    always_allowed: list[str] = [
        p.strip()
        for p in getattr(
            django_settings, "INGEST_ALWAYS_ALLOWED_PREFIXES", "/photos"
        ).split(",")
        if p.strip()
    ]

    try:
        path = validate_ingest_path(
            path, allowed_prefixes or None, always_allowed=always_allowed
        )
    except ValueError as exc:
        return {
            "success": False,
            "count": 0,
            "checksums_calculated": 0,
            "images_stored": 0,
            "thumbnails_retried": 0,
            "skipped_already_ingested": 0,
            "errors": [str(exc)],
        }

    # ----- Local fast path ------------------------------------------------
    if os.path.exists(path):
        if device is None:
            device = build_device_label(path)
        return run_ingest_local(
            path,
            device=device,
            recursive=recursive,
            calculate_checksum=calculate_checksum,
            store_images=store_images,
            resolution=resolution,
            log_path=log_path,
            retry_thumbnails=retry_thumbnails,
        )

    # ----- Docker path ----------------------------------------------------
    docker_enabled: bool = getattr(django_settings, "INGEST_DOCKER_ENABLED", False)
    if not docker_enabled:
        return {
            "success": False,
            "count": 0,
            "checksums_calculated": 0,
            "images_stored": 0,
            "thumbnails_retried": 0,
            "skipped_already_ingested": 0,
            "errors": [
                f"Path {path!r} does not exist in the current container namespace "
                "and INGEST_DOCKER_ENABLED is False. "
                "Either: (a) bind-mount the path into the worker/web services, "
                "(b) set INGEST_DOCKER_ENABLED=true and mount /var/run/docker.sock, "
                "or (c) use 'scripts/compose-ingest.sh' from the host instead."
            ],
        }

    if not allowed_prefixes:
        return {
            "success": False,
            "count": 0,
            "checksums_calculated": 0,
            "images_stored": 0,
            "thumbnails_retried": 0,
            "skipped_already_ingested": 0,
            "errors": [
                f"Path {path!r} does not exist locally and "
                "INGEST_ALLOWED_PATH_PREFIXES is not configured. "
                "Set it to the host mount roots you want to allow, e.g. "
                "INGEST_ALLOWED_PATH_PREFIXES=/mnt,/media."
            ],
        }

    # Resolve mount root if not supplied
    effective_mount_root = mount_root or resolve_mount_root(path)

    if device is None:
        device = build_device_label(path)

    return run_ingest_docker(
        path=path,
        mount_root=effective_mount_root,
        device=device,
        recursive=recursive,
        calculate_checksum=calculate_checksum,
        store_images=store_images,
        resolution=resolution,
        retry_thumbnails=retry_thumbnails,
    )
