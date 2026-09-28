"""Local filesystem storage adapter."""

from __future__ import annotations

import os
import shutil
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO, Iterator

from ..domain import MediaObject, StorageCapabilities


class LocalFilesystemAdapter:
    adapter_id = "local"

    def _path(self, path: str) -> Path:
        return Path(path).expanduser().resolve()

    def list_objects(self, path: str) -> Iterator[MediaObject]:
        root = self._path(path)
        if not root.is_dir():
            raise FileNotFoundError(f"Source directory does not exist: {root}")
        for directory, _, files in os.walk(root):
            for filename in sorted(files):
                yield self.get_object_info(str(Path(directory) / filename))

    def get_object_info(self, path: str) -> MediaObject:
        resolved = self._path(path)
        stat = resolved.stat()
        return MediaObject(
            adapter_id=self.adapter_id,
            object_id=f"{stat.st_dev}:{stat.st_ino}",
            path=str(resolved),
            name=resolved.name,
            size=stat.st_size,
            modified_time=datetime.fromtimestamp(stat.st_mtime, timezone.utc),
        )

    @contextmanager
    def open_read(self, path: str) -> Iterator[BinaryIO]:
        with self._path(path).open("rb") as stream:
            yield stream

    def ensure_directory(self, path: str) -> None:
        self._path(path).mkdir(parents=True, exist_ok=True)

    def copy(self, source: str, destination: str) -> None:
        destination_path = self._path(destination)
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination_path.with_name(destination_path.name + ".partial")
        try:
            shutil.copy2(self._path(source), temporary)
            os.replace(temporary, destination_path)
        finally:
            temporary.unlink(missing_ok=True)

    def move(self, source: str, destination: str) -> None:
        destination_path = self._path(destination)
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        source_path = self._path(source)
        try:
            os.replace(source_path, destination_path)
        except OSError:
            self.copy(str(source_path), str(destination_path))
            source_path.unlink()

    def delete(self, path: str) -> None:
        self._path(path).unlink()

    def exists(self, path: str) -> bool:
        return self._path(path).exists()

    def get_capabilities(self) -> StorageCapabilities:
        return StorageCapabilities(
            atomic_move=True,
            server_side_move=True,
            random_read=True,
            streaming_read=True,
            local_filesystem=True,
        )

    def healthcheck(self) -> None:
        Path.cwd().stat()
