"""Shared mount-root and bind-flag utilities for host-path CLI workflows.

This module provides path-validation and mount-resolution helpers used by both
the ingest runner (``photochart.ingest.runner``) and the generic
``scripts/compose-run.sh`` / ``scripts/compose-organize.sh`` wrappers.

Key functions
-------------
``validate_host_path(path, allowed_prefixes)``
    Normalise and security-check a raw path string (no Django dependency).
``resolve_mount_root(path)``
    Find the filesystem mount point for any path (Linux ``findmnt`` + fallback).
``collect_mount_roots(paths, skip_library_prefix)``
    Unique mount roots for a list of paths, skipping already-mounted prefixes.
``docker_bind_flags(mount_roots, mode)``
    Produce ``["-v", "/mnt/x:/mnt/x:ro", ...]`` flags for ``docker compose run``.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Paths that are never safe to bind-mount into a container.
DANGEROUS_PREFIXES: tuple[str, ...] = (
    "/proc",
    "/sys",
    "/dev",
    "/run/docker.sock",
    "/var/run/docker.sock",
)

#: Container-internal paths always considered valid without a Docker bind.
#: Overridable via the caller (e.g. INGEST_ALWAYS_ALLOWED_PREFIXES setting).
DEFAULT_ALWAYS_ALLOWED: tuple[str, ...] = ("/photos",)


# ---------------------------------------------------------------------------
# Path validation
# ---------------------------------------------------------------------------


def validate_host_path(
    path: str,
    allowed_prefixes: Optional[list[str]] = None,
    always_allowed: Optional[list[str]] = None,
) -> str:
    """Return the normalised absolute path or raise ``ValueError``.

    This function is intentionally free of Django dependencies so it can be
    used by host-side CLI code as well as in-container Django views.

    Args:
        path:             Raw path supplied by the caller.
        allowed_prefixes: If non-empty, the resolved path must start with at
                          least one of these prefixes *or* one of
                          *always_allowed*.  An empty/``None`` list disables
                          the prefix check entirely.
        always_allowed:   Prefixes that are always valid regardless of
                          *allowed_prefixes*.  Defaults to ``DEFAULT_ALWAYS_ALLOWED``
                          (``("/photos",)``).

    Returns:
        Resolved absolute path string.

    Raises:
        ValueError: If the path is empty, contains traversal sequences,
                    resolves to a dangerous root, or fails the prefix check.
    """
    if not path or not path.strip():
        raise ValueError("Path must not be empty.")

    if ".." in Path(path).parts:
        raise ValueError(f"Path traversal detected: {path!r}")

    resolved = os.path.realpath(os.path.abspath(path.strip()))

    for dangerous in DANGEROUS_PREFIXES:
        if resolved == dangerous or resolved.startswith(dangerous + "/"):
            raise ValueError(
                f"Path {resolved!r} is inside a restricted system path "
                f"({dangerous!r}). Bind-mounting this path is not allowed."
            )

    if resolved == "/":
        raise ValueError("Path must not be the filesystem root '/'.")

    if allowed_prefixes:
        _always = (
            list(always_allowed)
            if always_allowed is not None
            else list(DEFAULT_ALWAYS_ALLOWED)
        )
        all_allowed = allowed_prefixes + _always
        if not any(
            resolved == p.rstrip("/") or resolved.startswith(p.rstrip("/") + "/")
            for p in all_allowed
        ):
            raise ValueError(
                f"Path {resolved!r} is not under any allowed prefix. "
                f"Allowed: {allowed_prefixes}. "
                f"Always allowed: {_always}. "
                f"Add the appropriate root to INGEST_ALLOWED_PATH_PREFIXES."
            )

    return resolved


# ---------------------------------------------------------------------------
# Mount-point discovery (Linux)
# ---------------------------------------------------------------------------


def resolve_mount_root(path: str) -> str:
    """Return the filesystem mount root that contains *path*.

    Uses ``findmnt -T`` when available (Linux), falls back to the
    ``photochart.fs.device`` proc-mounts reader, then to the path's own
    directory.

    Args:
        path: Absolute path to a file or directory.

    Returns:
        Absolute path of the nearest mount point (never ``"/"``; falls back
        to the path's own directory when the mount is the root filesystem, so
        the bind-mount is as tight as possible).
    """
    # 1. findmnt – reliable on modern Linux (util-linux)
    try:
        result = subprocess.run(
            ["findmnt", "-T", path, "--output", "TARGET", "--noheadings", "--raw"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            mount = result.stdout.strip()
            if mount and mount != "/":
                return mount
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    # 2. /proc/mounts reader already in the codebase
    try:
        from photochart.fs.device import get_mount_point  # type: ignore[attr-defined]

        mount = get_mount_point(path)
        if mount and mount != "/":
            return mount
    except Exception:
        pass

    # 3. Last resort: tightest parent that actually exists
    p = Path(os.path.realpath(path))
    if p.is_file():
        p = p.parent
    return str(p)


# ---------------------------------------------------------------------------
# Collect unique mount roots for a set of paths
# ---------------------------------------------------------------------------


def collect_mount_roots(
    paths: list[str],
    *,
    skip_prefixes: Optional[list[str]] = None,
) -> list[str]:
    """Return the unique filesystem mount roots for *paths*.

    Paths whose resolved absolute form starts with any entry of
    *skip_prefixes* are excluded (they are already available inside the
    container via permanent volume mounts and do not need an extra bind).

    Args:
        paths:          List of absolute host paths (source, destination,
                        quarantine, etc.).
        skip_prefixes:  Prefixes to exclude from the result (e.g. ``["/photos"]``
                        for the default library mount).  Defaults to
                        ``list(DEFAULT_ALWAYS_ALLOWED)``.

    Returns:
        Deduplicated list of mount root strings in discovery order.
    """
    if skip_prefixes is None:
        skip_prefixes = list(DEFAULT_ALWAYS_ALLOWED)

    seen: set[str] = set()
    roots: list[str] = []
    for raw in paths:
        if not raw or not raw.strip():
            continue
        resolved = os.path.realpath(os.path.abspath(raw.strip()))
        # Skip paths already accessible via permanent volume mounts
        if any(
            resolved == p.rstrip("/") or resolved.startswith(p.rstrip("/") + "/")
            for p in skip_prefixes
        ):
            continue
        root = resolve_mount_root(resolved)
        if root not in seen:
            seen.add(root)
            roots.append(root)
    return roots


# ---------------------------------------------------------------------------
# Docker bind-flag generation
# ---------------------------------------------------------------------------


def docker_bind_flags(
    mount_roots: list[str],
    mode: str = "ro",
) -> list[str]:
    """Return ``docker compose run`` bind-mount flags for *mount_roots*.

    Each root produces a ``-v SRC:DST:MODE`` flag where SRC == DST (the
    host path is mapped at the same absolute path inside the container so
    that ingest/organize paths require no translation).

    Args:
        mount_roots: List of absolute host mount roots (from
                     :func:`collect_mount_roots` or :func:`resolve_mount_root`).
        mode:        Mount mode, either ``"ro"`` (read-only, default) or
                     ``"rw"`` (read-write).

    Returns:
        Flat list of flags ready to splice into a ``subprocess`` command list,
        e.g. ``["-v", "/mnt/cam:/mnt/cam:ro", "-v", "/run/media/x:/run/media/x:ro"]``.

    Raises:
        ValueError: If *mode* is not ``"ro"`` or ``"rw"``.
    """
    if mode not in ("ro", "rw"):
        raise ValueError(f"mode must be 'ro' or 'rw', got {mode!r}")

    flags: list[str] = []
    for root in mount_roots:
        root = root.rstrip("/") or "/"
        flags += ["-v", f"{root}:{root}:{mode}"]
    return flags
