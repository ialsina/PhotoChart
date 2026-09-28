"""pCloud Drive virtual-filesystem adapter."""

from __future__ import annotations

from pathlib import Path

from ..domain import OrganizerError, ErrorKind, StorageCapabilities
from .local import LocalFilesystemAdapter


class PCloudDriveAdapter(LocalFilesystemAdapter):
    """Local operations with conservative pCloud Drive capability reporting."""

    adapter_id = "pcloud_drive"

    def __init__(self, mount_root: str) -> None:
        self.mount_root = Path(mount_root).expanduser().resolve()

    def _path(self, path: str) -> Path:
        resolved = super()._path(path)
        try:
            resolved.relative_to(self.mount_root)
        except ValueError as error:
            raise OrganizerError(
                f"Path is outside pCloud Drive mount: {resolved}",
                ErrorKind.CONFIGURATION,
            ) from error
        return resolved

    def healthcheck(self) -> None:
        try:
            if not self.mount_root.is_dir():
                raise OSError("mount is not a directory")
            next(self.mount_root.iterdir(), None)
            self.mount_root.stat()
        except OSError as error:
            raise OrganizerError(
                f"pCloud Drive is unavailable: {self.mount_root}",
                ErrorKind.TRANSIENT,
            ) from error

    def get_capabilities(self) -> StorageCapabilities:
        return StorageCapabilities(
            atomic_move=False,
            server_side_move=False,
            random_read=True,
            streaming_read=True,
            local_filesystem=True,
        )
