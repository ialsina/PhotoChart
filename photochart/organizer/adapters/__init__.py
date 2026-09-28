"""Built-in storage adapters."""

from .local import LocalFilesystemAdapter
from .pcloud_drive import PCloudDriveAdapter
from ..config import OrganizerConfig
from ..storage import StorageAdapter


def build_adapter(config: OrganizerConfig) -> StorageAdapter:
    if config.adapter == "local":
        return LocalFilesystemAdapter()
    if config.adapter == "pcloud_drive":
        mount_root = config.adapter_options.get("mount_root")
        if not mount_root:
            raise ValueError("pcloud_drive adapter requires mount_root")
        return PCloudDriveAdapter(str(mount_root))
    raise ValueError(f"Unknown or unavailable adapter: {config.adapter}")


__all__ = ["LocalFilesystemAdapter", "PCloudDriveAdapter", "build_adapter"]
