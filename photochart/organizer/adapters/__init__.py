"""Built-in storage adapters."""

import os

from .local import LocalFilesystemAdapter
from .pcloud_drive import PCloudDriveAdapter
from .pcloud_api import PCloudApiAdapter
from .webdav import NextcloudAdapter, WebDavAdapter
from .sftp import SftpAdapter
from .s3 import S3Adapter
from ..config import OrganizerConfig
from ..storage import StorageAdapter


def _secret(options, name: str) -> str:
    environment_name = options.get(f"{name}_env")
    value = os.environ.get(str(environment_name)) if environment_name else None
    value = value or options.get(name)
    if not value:
        raise ValueError(f"adapter requires {name} or {name}_env")
    return str(value)


def build_adapter(config: OrganizerConfig) -> StorageAdapter:
    options = config.adapter_options
    if config.adapter == "local":
        return LocalFilesystemAdapter()
    if config.adapter == "pcloud_drive":
        mount_root = options.get("mount_root")
        if not mount_root:
            raise ValueError("pcloud_drive adapter requires mount_root")
        return PCloudDriveAdapter(str(mount_root))
    if config.adapter == "pcloud_api":
        return PCloudApiAdapter(
            _secret(options, "access_token"),
            endpoint=str(options.get("endpoint", "https://api.pcloud.com")),
        )
    if config.adapter in {"webdav", "nextcloud"}:
        adapter_class = (
            NextcloudAdapter if config.adapter == "nextcloud" else WebDavAdapter
        )
        return adapter_class(
            str(options["endpoint"]),
            _secret(options, "username"),
            _secret(options, "password"),
        )
    if config.adapter == "sftp":
        return SftpAdapter(
            str(options["host"]),
            _secret(options, "username"),
            port=int(options.get("port", 22)),
            password=(
                _secret(options, "password")
                if options.get("password") or options.get("password_env")
                else None
            ),
            key_filename=options.get("key_filename"),
            known_hosts=options.get("known_hosts"),
        )
    if config.adapter == "s3":
        access_key = options.get("access_key_id")
        if options.get("access_key_id_env"):
            access_key = os.environ.get(str(options["access_key_id_env"]))
        secret_key = options.get("secret_access_key")
        if options.get("secret_access_key_env"):
            secret_key = os.environ.get(str(options["secret_access_key_env"]))
        return S3Adapter(
            str(options["bucket"]),
            endpoint_url=options.get("endpoint_url"),
            region_name=options.get("region_name"),
            access_key_id=access_key,
            secret_access_key=secret_key,
        )
    raise ValueError(f"Unknown or unavailable adapter: {config.adapter}")


__all__ = [
    "LocalFilesystemAdapter",
    "NextcloudAdapter",
    "PCloudApiAdapter",
    "PCloudDriveAdapter",
    "S3Adapter",
    "SftpAdapter",
    "WebDavAdapter",
    "build_adapter",
]
