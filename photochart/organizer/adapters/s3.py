"""S3 and S3-compatible object storage adapter."""

from __future__ import annotations

import hashlib
import posixpath
from contextlib import contextmanager
from typing import BinaryIO, Iterator

from ..domain import MediaObject, StorageCapabilities


class S3Adapter:
    adapter_id = "s3"

    def __init__(
        self,
        bucket: str,
        *,
        endpoint_url: str | None = None,
        region_name: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        client=None,
    ) -> None:
        self.bucket = bucket
        if client is not None:
            self.client = client
            return
        try:
            import boto3
        except ImportError as error:
            raise RuntimeError(
                "S3 support requires the 'boto3' optional dependency"
            ) from error
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            region_name=region_name,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
        )

    def _key(self, path: str) -> str:
        prefix = f"s3://{self.bucket}/"
        if path.startswith(prefix):
            return path[len(prefix) :]
        return path.lstrip("/")

    def _path(self, key: str) -> str:
        return "/" + key.lstrip("/")

    def list_objects(self, path: str) -> Iterator[MediaObject]:
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=self._key(path)):
            for item in page.get("Contents", []):
                key = item["Key"]
                if key.endswith("/"):
                    continue
                yield MediaObject(
                    self.adapter_id,
                    f"{key}:{item.get('VersionId', item.get('ETag', ''))}",
                    self._path(key),
                    posixpath.basename(key),
                    item["Size"],
                    item.get("LastModified"),
                    metadata={"etag": item.get("ETag")},
                )

    def get_object_info(self, path: str) -> MediaObject:
        key = self._key(path)
        item = self.client.head_object(Bucket=self.bucket, Key=key)
        return MediaObject(
            self.adapter_id,
            f"{key}:{item.get('VersionId', item.get('ETag', ''))}",
            self._path(key),
            posixpath.basename(key),
            item["ContentLength"],
            item.get("LastModified"),
            item.get("ContentType"),
            item,
        )

    @contextmanager
    def open_read(self, path: str) -> Iterator[BinaryIO]:
        body = self.client.get_object(Bucket=self.bucket, Key=self._key(path))["Body"]
        try:
            yield body
        finally:
            body.close()

    def ensure_directory(self, path: str) -> None:
        return None

    def copy(self, source: str, destination: str) -> None:
        self.client.copy(
            {"Bucket": self.bucket, "Key": self._key(source)},
            self.bucket,
            self._key(destination),
        )

    def _digest(self, path: str) -> str:
        digest = hashlib.sha256()
        with self.open_read(path) as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def move(self, source: str, destination: str) -> None:
        source_info = self.get_object_info(source)
        self.copy(source, destination)
        destination_info = self.get_object_info(destination)
        if source_info.size != destination_info.size:
            self.delete(destination)
            raise IOError("S3 copy size verification failed")

        source_checksum = source_info.metadata.get("ChecksumSHA256")
        destination_checksum = destination_info.metadata.get("ChecksumSHA256")
        if source_checksum and destination_checksum:
            verified = source_checksum == destination_checksum
        else:
            verified = self._digest(source) == self._digest(destination)
        if not verified:
            self.delete(destination)
            raise IOError("S3 copy content verification failed")
        self.delete(source)

    def delete(self, path: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=self._key(path))

    def exists(self, path: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=self._key(path))
            return True
        except Exception as error:
            response = getattr(error, "response", {})
            code = str(response.get("Error", {}).get("Code", ""))
            if code in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise

    def get_capabilities(self) -> StorageCapabilities:
        return StorageCapabilities(
            atomic_move=False,
            server_side_move=False,
            random_read=True,
            streaming_read=True,
            object_storage=True,
            resumable_transfer=True,
        )

    def healthcheck(self) -> None:
        self.client.head_bucket(Bucket=self.bucket)
