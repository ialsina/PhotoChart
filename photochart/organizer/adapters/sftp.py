"""SFTP storage adapter with host-key verification."""

from __future__ import annotations

import posixpath
import stat
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import BinaryIO, Iterator

from ..domain import MediaObject, StorageCapabilities


class SftpAdapter:
    adapter_id = "sftp"

    def __init__(
        self,
        host: str,
        username: str,
        *,
        port: int = 22,
        password: str | None = None,
        key_filename: str | None = None,
        known_hosts: str | None = None,
        timeout: float = 30,
    ) -> None:
        try:
            import paramiko
        except ImportError as error:
            raise RuntimeError(
                "SFTP support requires the 'paramiko' optional dependency"
            ) from error
        self._paramiko = paramiko
        self.client = paramiko.SSHClient()
        if known_hosts:
            self.client.load_host_keys(known_hosts)
        else:
            self.client.load_system_host_keys()
        self.client.set_missing_host_key_policy(paramiko.RejectPolicy())
        self.client.connect(
            host,
            port=port,
            username=username,
            password=password,
            key_filename=key_filename,
            timeout=timeout,
        )
        self.sftp = self.client.open_sftp()

    def list_objects(self, path: str) -> Iterator[MediaObject]:
        for entry in self.sftp.listdir_attr(path):
            child = posixpath.join(path, entry.filename)
            if stat.S_ISDIR(entry.st_mode):
                yield from self.list_objects(child)
            elif stat.S_ISREG(entry.st_mode):
                yield MediaObject(
                    self.adapter_id,
                    f"{entry.st_ino}:{entry.st_mtime}:{entry.st_size}",
                    child,
                    entry.filename,
                    entry.st_size,
                    datetime.fromtimestamp(entry.st_mtime, timezone.utc),
                )

    def get_object_info(self, path: str) -> MediaObject:
        entry = self.sftp.stat(path)
        return MediaObject(
            self.adapter_id,
            f"{entry.st_ino}:{entry.st_mtime}:{entry.st_size}",
            path,
            posixpath.basename(path),
            entry.st_size,
            datetime.fromtimestamp(entry.st_mtime, timezone.utc),
        )

    @contextmanager
    def open_read(self, path: str) -> Iterator[BinaryIO]:
        with self.sftp.open(path, "rb") as stream:
            yield stream

    def ensure_directory(self, path: str) -> None:
        current = ""
        for part in path.strip("/").split("/"):
            current += "/" + part
            try:
                self.sftp.mkdir(current)
            except OSError:
                self.sftp.stat(current)

    def copy(self, source: str, destination: str) -> None:
        with self.sftp.open(source, "rb") as input_stream:
            with self.sftp.open(destination + ".partial", "wb") as output_stream:
                for chunk in iter(lambda: input_stream.read(1024 * 1024), b""):
                    output_stream.write(chunk)
        self.sftp.rename(destination + ".partial", destination)

    def move(self, source: str, destination: str) -> None:
        self.sftp.rename(source, destination)

    def delete(self, path: str) -> None:
        self.sftp.remove(path)

    def exists(self, path: str) -> bool:
        try:
            self.sftp.stat(path)
            return True
        except FileNotFoundError:
            return False

    def get_capabilities(self) -> StorageCapabilities:
        return StorageCapabilities(
            server_side_move=True,
            streaming_read=True,
            random_read=True,
        )

    def healthcheck(self) -> None:
        self.sftp.stat(".")

    def close(self) -> None:
        self.sftp.close()
        self.client.close()
