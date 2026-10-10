"""Probe mounted volumes for filesystem UUID and block-device metadata."""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from photochart.fs.device import get_mount_point_from_file

_RFC_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
# vfat/exfat volume serial as reported by lsblk/blkid (32-bit, not RFC 128-bit).
_FAT_VOLUME_SERIAL_RE = re.compile(r"^[0-9a-f]{4}-[0-9a-f]{4}$", re.IGNORECASE)
_FAT_VOLUME_SERIAL_COMPACT_RE = re.compile(r"^[0-9a-f]{8}$", re.IGNORECASE)


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
    """Normalize a filesystem UUID string, or return None if invalid.

    Accepts RFC 128-bit UUIDs (ext4, btrfs, NTFS, …) and vfat/exfat volume
    serials in ``XXXX-XXXX`` form (or eight hex digits without a dash).
    """
    if not value or value in ("-", ""):
        return None
    cleaned = value.strip().lower()
    if _RFC_UUID_RE.match(cleaned):
        return cleaned
    if _FAT_VOLUME_SERIAL_RE.match(cleaned):
        return cleaned
    if _FAT_VOLUME_SERIAL_COMPACT_RE.match(cleaned):
        return f"{cleaned[:4]}-{cleaned[4:]}"
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


def synthetic_block_filesystem_uuid(source: str) -> str:
    """Stable synthetic id for a block device path when no filesystem UUID exists."""
    resolved = _resolve_partition_source(source)
    digest = hashlib.sha256(resolved.encode("utf-8")).hexdigest()[:32]
    return f"photchart:block:{digest}"


def volume_filesystem_uuid(probe: StorageProbeResult, catalog_device: str) -> str:
    """Return the catalog filesystem_uuid for a probe result."""
    return resolve_volume_identity(probe, catalog_device)


def resolve_volume_identity(probe: StorageProbeResult, catalog_device: str) -> str:
    """Return the catalog ``filesystem_uuid`` for a probe result."""
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
            return synthetic_block_filesystem_uuid(source)
    return synthetic_fuse_filesystem_uuid(
        mount or catalog_device, fstype or "unknown", source or catalog_device
    )


def _resolve_partition_source(source: str) -> str:
    if not source.startswith("/dev/"):
        return source
    try:
        return os.path.realpath(source)
    except OSError:
        return source


def _blkid_filesystem_uuid(dev_path: str) -> Optional[str]:
    resolved = _resolve_partition_source(dev_path)
    try:
        result = subprocess.run(
            ["blkid", "-o", "value", "-s", "UUID", resolved],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return canonical_filesystem_uuid(result.stdout.strip())
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return None


def _lsblk_filesystem_uuid(dev_path: str) -> Optional[str]:
    resolved = _resolve_partition_source(dev_path)
    try:
        result = subprocess.run(
            ["lsblk", "-no", "UUID", resolved],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return canonical_filesystem_uuid(result.stdout.strip().splitlines()[0])
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return None


def _fill_partition_filesystem_uuid(result: StorageProbeResult) -> None:
    if canonical_filesystem_uuid(result.filesystem_uuid):
        return
    source = result.source or ""
    if not source.startswith("/dev/"):
        return
    uuid = _blkid_filesystem_uuid(source) or _lsblk_filesystem_uuid(source)
    if uuid:
        result.filesystem_uuid = uuid


def _lsblk_parent_disk_identity(dev_path: str) -> dict[str, str]:
    """Return vendor, model, serial from the parent block device (disk), not the partition."""
    if not dev_path.startswith("/dev/"):
        return {}
    resolved = _resolve_partition_source(dev_path)
    try:
        pk_result = subprocess.run(
            ["lsblk", "-no", "PKNAME", resolved],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if pk_result.returncode != 0 or not pk_result.stdout.strip():
            disk_path = resolved
        else:
            pkname = pk_result.stdout.strip().splitlines()[0].strip()
            if not pkname:
                disk_path = resolved
            else:
                disk_path = f"/dev/{pkname}"
                for _ in range(16):
                    parent = subprocess.run(
                        ["lsblk", "-no", "PKNAME", disk_path],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    if parent.returncode != 0 or not parent.stdout.strip():
                        break
                    next_pk = parent.stdout.strip().splitlines()[0].strip()
                    if not next_pk:
                        break
                    next_path = f"/dev/{next_pk}"
                    if next_path == disk_path:
                        break
                    disk_path = next_path

        id_result = subprocess.run(
            ["lsblk", "-no", "MODEL,SERIAL,VENDOR", disk_path],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if id_result.returncode != 0 or not id_result.stdout.strip():
            return {}
        parts = id_result.stdout.strip().splitlines()[0].split(None, 2)
        fields: dict[str, str] = {}
        if len(parts) >= 1 and parts[0] not in ("", "-"):
            fields["model"] = parts[0]
        if len(parts) >= 2 and parts[1] not in ("", "-"):
            fields["serial"] = parts[1]
        if len(parts) >= 3 and parts[2] not in ("", "-"):
            fields["vendor"] = parts[2]
        return fields
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return {}


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
        if len(parts) < 3:
            return {}
        first = parts[0].strip()
        # findmnt omits an empty UUID column; the line then starts with SOURCE.
        if (
            first.startswith("/dev/")
            or first.startswith("//")
            or (":" in first and canonical_filesystem_uuid(first) is None)
        ):
            out = {
                "uuid": "-",
                "source": first,
                "fstype": parts[1].strip(),
                "target": parts[2].strip(),
            }
            if len(parts) >= 4:
                out["size"] = parts[3].strip()
            return out
        if len(parts) < 4:
            return {}
        out = {
            "uuid": first,
            "source": parts[1].strip(),
            "fstype": parts[2].strip(),
            "target": parts[3].strip(),
        }
        if len(parts) >= 5:
            out["size"] = parts[4].strip()
        return out
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

    _fill_partition_filesystem_uuid(result)

    if not deep:
        return result

    if source.startswith("/dev/"):
        identity = _lsblk_parent_disk_identity(source)
        if identity.get("vendor"):
            result.vendor = identity["vendor"]
        if identity.get("model"):
            result.model = identity["model"]
        if identity.get("serial"):
            result.serial = identity["serial"]

    return result


def resolve_filesystem_uuid(
    path: str, catalog_device: str, *, deep: bool = True
) -> str:
    """Probe *path* and return the catalog ``filesystem_uuid`` string."""
    probe = probe_storage_from_path(path, deep=deep)
    return resolve_volume_identity(probe, catalog_device)
