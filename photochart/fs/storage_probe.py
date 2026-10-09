"""Probe mounted volumes for filesystem UUID and block-device metadata."""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from photochart.fs.device import get_mount_point_from_file, unescape_mounts_path

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


@dataclass
class StorageProbeResult:
    """Raw probe data for a path on a mounted volume."""

    filesystem_uuid: Optional[str] = None
    capacity_bytes: Optional[int] = None
    vendor: Optional[str] = None
    model: Optional[str] = None
    serial: Optional[str] = None
    source: Optional[str] = None
    fstype: Optional[str] = None
    mount_root: Optional[str] = None
    notes: str = ""


def canonical_filesystem_uuid(value: Optional[str]) -> Optional[str]:
    """Normalize a filesystem UUID string, or return None if invalid."""
    if not value or value in ("-", ""):
        return None
    cleaned = value.strip().lower()
    if _UUID_RE.match(cleaned):
        return cleaned
    return None


def legacy_filesystem_uuid(catalog_device: str) -> str:
    """Synthetic volume id for pre-migration rows keyed by device label."""
    digest = hashlib.sha256(catalog_device.encode("utf-8")).hexdigest()[:32]
    return f"photchart:legacy:{digest}"


def synthetic_fuse_filesystem_uuid(mount_root: str, fstype: str, source: str) -> str:
    """Stable synthetic id for FUSE/network volumes without a kernel UUID."""
    mount_norm = os.path.normpath(mount_root)
    material = f"{mount_norm}\0{fstype}\0{source}"
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]
    return f"photchart:fuse:{digest}"


def volume_filesystem_uuid(probe: StorageProbeResult, catalog_device: str) -> str:
    """Return the catalog filesystem_uuid for a probe result."""
    real = canonical_filesystem_uuid(probe.filesystem_uuid)
    if real:
        return real
    mount = probe.mount_root or ""
    fstype = probe.fstype or ""
    source = probe.source or ""
    if mount or fstype or source:
        if fstype.startswith("fuse") or probe.notes in (
            "fuse_cloud",
            "network_mount",
        ):
            return synthetic_fuse_filesystem_uuid(mount, fstype, source)
        if not fstype.startswith("fuse") and source.startswith("/dev/"):
            return legacy_filesystem_uuid(catalog_device)
    return synthetic_fuse_filesystem_uuid(
        mount or catalog_device, fstype or "unknown", source or catalog_device
    )


def _statvfs_capacity_bytes(path: str) -> Optional[int]:
    try:
        st = os.statvfs(path)
        return int(st.f_frsize) * int(st.f_blocks)
    except OSError:
        return None


def _run_findmnt(path: str) -> dict[str, str]:
    try:
        result = subprocess.run(
            [
                "findmnt",
                "-T",
                path,
                "--output",
                "UUID,SOURCE,FSTYPE,TARGET,SIZE",
                "--bytes",
                "--noheadings",
                "--raw",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return {}
        line = result.stdout.strip()
        if not line:
            return {}
        parts = line.split(None, 4)
        if len(parts) < 4:
            return {}
        out = {
            "uuid": parts[0].strip(),
            "source": parts[1].strip(),
            "fstype": parts[2].strip(),
            "target": parts[3].strip(),
        }
        if len(parts) >= 5:
            try:
                out["size"] = parts[4].strip()
            except ValueError:
                pass
        return out
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return {}


def _lsblk_fields(source: str) -> dict[str, str]:
    if not source.startswith("/dev/"):
        return {}
    dev_path = source
    try:
        result = subprocess.run(
            [
                "lsblk",
                "-no",
                "NAME,PKNAME,MODEL,SERIAL,VENDOR,SIZE",
                dev_path,
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return {}
        line = result.stdout.strip().splitlines()
        if not line:
            return {}
        parts = line[0].split(None, 5)
        fields: dict[str, str] = {}
        if len(parts) >= 1:
            fields["name"] = parts[0]
        if len(parts) >= 2:
            fields["pkname"] = parts[1]
        if len(parts) >= 3:
            fields["model"] = parts[2]
        if len(parts) >= 4:
            fields["serial"] = parts[3]
        if len(parts) >= 5:
            fields["vendor"] = parts[4]
        if len(parts) >= 6:
            fields["size"] = parts[5]
        pk = fields.get("pkname", "").strip()
        if pk and (not fields.get("vendor") or not fields.get("model")):
            parent = subprocess.run(
                [
                    "lsblk",
                    "-no",
                    "MODEL,SERIAL,VENDOR",
                    f"/dev/{pk}",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if parent.returncode == 0 and parent.stdout.strip():
                pparts = parent.stdout.strip().split(None, 2)
                if len(pparts) >= 1 and not fields.get("model"):
                    fields["model"] = pparts[0]
                if len(pparts) >= 2 and not fields.get("serial"):
                    fields["serial"] = pparts[1]
                if len(pparts) >= 3 and not fields.get("vendor"):
                    fields["vendor"] = pparts[2]
        return fields
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return {}


def _is_fuse_or_network(fstype: str, source: str) -> bool:
    if fstype.startswith("fuse"):
        return True
    if fstype in ("nfs", "nfs4", "cifs", "smb3", "smbfs"):
        return True
    if source.startswith("//") or (":" in source and not source.startswith("/dev/")):
        return True
    return False


def probe_storage_from_path(
    path: str,
    *,
    proc_mounts_path: str = "/proc/mounts",
    deep: bool = True,
) -> StorageProbeResult:
    """Probe volume metadata for *path* (must be visible in the current namespace)."""
    result = StorageProbeResult()
    path_obj = Path(path)
    probe_path = str(path_obj.resolve()) if path_obj.exists() else path
    if not path_obj.exists():
        probe_path = path

    fm = _run_findmnt(probe_path)
    if fm:
        result.filesystem_uuid = canonical_filesystem_uuid(fm.get("uuid"))
        result.source = fm.get("source") or None
        result.fstype = fm.get("fstype") or None
        result.mount_root = fm.get("target") or None
        if fm.get("size"):
            try:
                result.capacity_bytes = int(fm["size"])
            except ValueError:
                pass

    if result.mount_root is None:
        result.mount_root = get_mount_point_from_file(
            probe_path, proc_mounts_path=proc_mounts_path
        )

    if result.capacity_bytes is None and result.mount_root:
        cap = _statvfs_capacity_bytes(result.mount_root)
        if cap is not None:
            result.capacity_bytes = cap
    elif result.capacity_bytes is None:
        cap = _statvfs_capacity_bytes(probe_path)
        if cap is not None:
            result.capacity_bytes = cap

    fstype = result.fstype or ""
    source = result.source or ""

    if _is_fuse_or_network(fstype, source):
        result.notes = "fuse_cloud" if fstype.startswith("fuse") else "network_mount"
        return result

    if not deep:
        return result

    if source.startswith("/dev/"):
        blk = _lsblk_fields(source)
        if blk.get("vendor"):
            result.vendor = blk["vendor"]
        if blk.get("model"):
            result.model = blk["model"]
        if blk.get("serial"):
            result.serial = blk["serial"]

    return result


def resolve_filesystem_uuid(
    path: str, catalog_device: str, *, deep: bool = True
) -> str:
    """Probe *path* and return the catalog ``filesystem_uuid`` string."""
    probe = probe_storage_from_path(path, deep=deep)
    return volume_filesystem_uuid(probe, catalog_device)
