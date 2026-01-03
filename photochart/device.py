import socket
from pathlib import Path
from typing import Optional
import re


def unescape_mounts_path(path: str) -> str:
    """Unescape a path from /proc/mounts.

    /proc/mounts uses octal escape sequences:
    - \040 = space
    - \011 = tab
    - \012 = newline
    - \134 = backslash
    """

    def replace_octal(match):
        return chr(int(match.group(1), 8))

    # Replace octal escape sequences like \040, \011, etc.
    return re.sub(r"\\([0-7]{3})", replace_octal, path)


def sanitize_label(label: str) -> str:
    """Sanitize a device label by decoding escape sequences.

    Handles:
    - Hex escape sequences: \x20, \x0A, etc.
    - Octal escape sequences: \040, \011, etc.
    - URL encoding (via urllib.parse.unquote)
    """
    # First, try URL decoding (handles %20, etc.)
    try:
        import urllib.parse

        label = urllib.parse.unquote(label)
    except Exception:
        pass

    # Handle hex escape sequences like \x20, \x0A
    def replace_hex(match):
        return chr(int(match.group(1), 16))

    label = re.sub(r"\\x([0-9a-fA-F]{2})", replace_hex, label)

    # Handle octal escape sequences like \040, \011
    def replace_octal(match):
        return chr(int(match.group(1), 8))

    label = re.sub(r"\\([0-7]{3})", replace_octal, label)

    return label


def get_mount_point(file_path: str) -> Optional[str]:
    """Get the mount point for a file path.

    Args:
        file_path: Path to a file

    Returns:
        Mount point path if found, None if on root filesystem or not found
    """
    try:
        path_obj = Path(file_path)
        if not path_obj.exists():
            # Path doesn't exist, try to get mount point from parent directory
            path_obj = path_obj.parent
            while path_obj != path_obj.parent and not path_obj.exists():
                path_obj = path_obj.parent
            if not path_obj.exists():
                return None

        # Resolve to absolute path
        abs_path = path_obj.resolve()

        # Read /proc/mounts to find mount points (Linux)
        try:
            with open("/proc/mounts", "r") as f:
                mounts = []
                for line in f:
                    parts = line.split()
                    if len(parts) >= 2:
                        device = unescape_mounts_path(parts[0])
                        mount = unescape_mounts_path(parts[1])
                        fstype = parts[2] if len(parts) > 2 else ""
                        mounts.append((device, mount, fstype))

                # Sort by mount path length (longest first) to match most specific mount
                mounts.sort(key=lambda x: len(x[1]), reverse=True)

                # Find the mount point that contains our path
                for device, mount, fstype in mounts:
                    try:
                        mount_path = Path(mount)
                        if mount_path.exists() and abs_path.is_relative_to(mount_path):
                            # return mount point if it's not the root filesystem
                            if mount != "/":
                                return mount
                            return None
                    except (ValueError, OSError):
                        # Path comparison failed, skip
                        continue
        except (OSError, IOError):
            # /proc/mounts not available (not Linux or permission issue)
            pass

        return None
    except Exception:
        return None


def get_device_name(file_path: Optional[str] = None) -> str:
    """Get the device/filesystem identifier for a file path.

    Identifies the filesystem/device where files are stored, not just the hostname.
    For files on the root filesystem, returns the hostname. For files on mounted
    filesystems (external drives, network mounts, etc.), returns a device identifier
    such as mount point name, device label, or UUID.

    Args:
        file_path: Optional path to a file. If provided, determines the device
            for that specific path. If None, returns hostname for local filesystem.

    Returns:
        Device identifier string (hostname, mount point, device label, or 'unknown')
    """
    # If no path provided, return hostname for local filesystem
    if file_path is None:
        try:
            return socket.gethostname()
        except Exception:
            return "unknown"

    try:
        path_obj = Path(file_path)
        if not path_obj.exists():
            # Path doesn't exist, try to get device from parent directory
            path_obj = path_obj.parent
            while path_obj != path_obj.parent and not path_obj.exists():
                path_obj = path_obj.parent
            if not path_obj.exists():
                # Can't determine device, fall back to hostname
                try:
                    return socket.gethostname()
                except Exception:
                    return "unknown"

        # Resolve to absolute path
        abs_path = path_obj.resolve()

        # Try to find the mount point for this path
        mount_point = None
        device_info = None

        # Read /proc/mounts to find mount points (Linux)
        try:
            with open("/proc/mounts", "r") as f:
                mounts = []
                for line in f:
                    parts = line.split()
                    if len(parts) >= 2:
                        device = unescape_mounts_path(parts[0])
                        mount = unescape_mounts_path(parts[1])
                        fstype = parts[2] if len(parts) > 2 else ""
                        mounts.append((device, mount, fstype))

                # Sort by mount path length (longest first) to match most specific mount
                mounts.sort(key=lambda x: len(x[1]), reverse=True)

                # Find the mount point that contains our path
                for device, mount, fstype in mounts:
                    try:
                        mount_path = Path(mount)
                        if mount_path.exists() and abs_path.is_relative_to(mount_path):
                            mount_point = mount
                            device_info = (device, fstype)
                            break
                    except (ValueError, OSError):
                        # Path comparison failed, skip
                        continue
        except (OSError, IOError):
            # /proc/mounts not available (not Linux or permission issue)
            pass

        # If we found a mount point, try to identify the device
        if mount_point and device_info:
            device, fstype = device_info

            # Try to get device label (for external drives) FIRST
            # This ensures external devices are identified even if mounted at /
            if device.startswith("/dev/"):
                device_name = device[5:]  # Remove /dev/ prefix

                # Try to find label in /dev/disk/by-label/
                try:
                    by_label = Path("/dev/disk/by-label")
                    if by_label.exists():
                        for label_link in by_label.iterdir():
                            try:
                                target = label_link.readlink()
                                if target.name == device_name or str(target) == device:
                                    # Found label, use it
                                    label = label_link.name
                                    # Sanitize label (handles URL encoding, hex/octal escape sequences)
                                    label = sanitize_label(label)
                                    return f"{label} ({mount_point})"
                            except (OSError, ValueError):
                                continue
                except (OSError, IOError):
                    pass

                # Try to find UUID in /dev/disk/by-uuid/
                try:
                    by_uuid = Path("/dev/disk/by-uuid")
                    if by_uuid.exists():
                        for uuid_link in by_uuid.iterdir():
                            try:
                                target = uuid_link.readlink()
                                if target.name == device_name or str(target) == device:
                                    uuid = uuid_link.name
                                    # If mount point is /, check if it's actually the root filesystem
                                    if mount_point == "/":
                                        # Find the actual root filesystem device from /proc/mounts
                                        root_device = None
                                        try:
                                            with open("/proc/mounts", "r") as f:
                                                for line in f:
                                                    parts = line.split()
                                                    if len(parts) >= 2:
                                                        mount = unescape_mounts_path(
                                                            parts[1]
                                                        )
                                                        if mount == "/":
                                                            root_device = (
                                                                unescape_mounts_path(
                                                                    parts[0]
                                                                )
                                                            )
                                                            break
                                        except (OSError, IOError):
                                            pass

                                        # If this is the root filesystem device, return hostname
                                        if root_device and device == root_device:
                                            try:
                                                return socket.gethostname()
                                            except Exception:
                                                return "local"
                                        # Otherwise, it's an external device mounted at / (unusual)
                                        # Use device name with UUID
                                        return f"{device_name} [{uuid[:8]}]"
                                    else:
                                        # Normal case: use mount point name with UUID
                                        mount_name = (
                                            Path(mount_point).name or mount_point
                                        )
                                        return f"{mount_name} [{uuid[:8]}]"
                            except (OSError, ValueError):
                                continue
                except (OSError, IOError):
                    pass

                # For network filesystems, extract server/share info
                if fstype in ["nfs", "cifs", "smbfs"]:
                    # Extract server name from device string
                    # Format might be server:/path or //server/share
                    if ":" in device:
                        server = device.split(":")[0]
                        return f"{server} ({mount_point})"
                    elif device.startswith("//"):
                        parts = device[2:].split("/", 1)
                        server = parts[0] if parts else "network"
                        return f"{server} ({mount_point})"

                # Before using device name, check if it's the root filesystem
                # Only do this if no label/UUID was found above
                if mount_point == "/":
                    # Find the actual root filesystem device from /proc/mounts
                    root_device = None
                    try:
                        with open("/proc/mounts", "r") as f:
                            for line in f:
                                parts = line.split()
                                if len(parts) >= 2:
                                    mount = unescape_mounts_path(parts[1])
                                    if mount == "/":
                                        root_device = unescape_mounts_path(parts[0])
                                        break
                    except (OSError, IOError):
                        pass

                    # Only treat as root filesystem if this device matches the actual root device
                    if root_device and device == root_device:
                        try:
                            return socket.gethostname()
                        except Exception:
                            return "local"
                    # Otherwise, it's an external device mounted at / (unusual but possible)
                    # Continue to use device name below

                # Use device name with mount point
                mount_name = Path(mount_point).name or mount_point
                return f"{device_name} ({mount_name})"

            # For other device types, use mount point name
            mount_name = Path(mount_point).name or mount_point
            return mount_name

        # Fallback: check if path is on root filesystem
        # If we can't determine mount point, assume local filesystem
        try:
            return socket.gethostname()
        except Exception:
            return "local"

    except Exception:
        # If anything fails, fall back to hostname
        try:
            return socket.gethostname()
        except Exception:
            return "unknown"
