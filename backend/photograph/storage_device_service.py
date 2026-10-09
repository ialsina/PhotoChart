"""Resolve and persist :class:`StorageDevice` rows during ingest."""

from __future__ import annotations

from typing import Set, Tuple

from django.db import transaction
from django.utils import timezone

from photochart.fs.storage_probe import (
    StorageProbeResult,
    legacy_filesystem_uuid,
    probe_storage_from_path,
    resolve_volume_identity,
)

from .models import PhotoPath, StorageDevice


def _merge_probe_into_device(
    device: StorageDevice, probe: StorageProbeResult, catalog_device: str
) -> None:
    if catalog_device:
        device.catalog_device = catalog_device
    if probe.capacity_bytes is not None:
        device.capacity_bytes = probe.capacity_bytes
    if probe.vendor:
        device.vendor = probe.vendor
    if probe.model:
        device.model = probe.model
    if probe.serial:
        device.serial = probe.serial
    if probe.source:
        device.source = probe.source
    if probe.fstype:
        device.fstype = probe.fstype
    if probe.mount_root:
        device.mount_root = probe.mount_root
    if probe.notes:
        device.probe_notes = probe.notes
    device.probed_at = timezone.now()


def _collect_old_volume_uuids(
    catalog_device: str,
    new_uuid: str,
    *,
    mount_root: str | None = None,
) -> Set[str]:
    """UUIDs that may hold existing catalog rows for this volume before re-key."""
    old: Set[str] = set()
    old.add(legacy_filesystem_uuid(catalog_device))

    for fs_uuid in (
        PhotoPath.objects.filter(device=catalog_device)
        .values_list("filesystem_uuid", flat=True)
        .distinct()
    ):
        if fs_uuid and fs_uuid != new_uuid:
            old.add(fs_uuid)

    for fs_uuid in StorageDevice.objects.filter(
        catalog_device=catalog_device
    ).values_list("filesystem_uuid", flat=True):
        if fs_uuid and fs_uuid != new_uuid:
            old.add(fs_uuid)

    if mount_root:
        for fs_uuid in StorageDevice.objects.filter(mount_root=mount_root).values_list(
            "filesystem_uuid", flat=True
        ):
            if fs_uuid and fs_uuid != new_uuid:
                old.add(fs_uuid)

    old.discard(new_uuid)
    return old


def _resolve_path_collisions(old_uuid: str, new_uuid: str) -> None:
    """Drop duplicate paths that would violate (path, filesystem_uuid) after re-key.

    When both old_uuid and new_uuid rows exist for the same path, keep the row
    with a linked photograph, or the newer ``updated_at``, and delete the other.
    """
    old_paths = PhotoPath.objects.filter(filesystem_uuid=old_uuid)
    for old_row in old_paths:
        conflict = PhotoPath.objects.filter(
            path=old_row.path, filesystem_uuid=new_uuid
        ).first()
        if not conflict:
            continue
        keep_old = False
        if old_row.photograph_id and not conflict.photograph_id:
            keep_old = True
        elif old_row.photograph_id and conflict.photograph_id:
            keep_old = old_row.updated_at >= conflict.updated_at
        elif not old_row.photograph_id and not conflict.photograph_id:
            keep_old = old_row.updated_at >= conflict.updated_at
        if keep_old:
            conflict.delete()
        else:
            old_row.delete()


def migrate_volume_identity(
    catalog_device: str,
    probe: StorageProbeResult,
    new_uuid: str,
) -> StorageDevice:
    """Re-key PhotoPath rows and merge StorageDevice metadata for *new_uuid*."""
    with transaction.atomic():
        old_uuids = _collect_old_volume_uuids(
            catalog_device,
            new_uuid,
            mount_root=probe.mount_root,
        )
        for old_uuid in old_uuids:
            _resolve_path_collisions(old_uuid, new_uuid)

        sd, _created = StorageDevice.objects.update_or_create(
            filesystem_uuid=new_uuid,
            defaults={"catalog_device": catalog_device},
        )
        _merge_probe_into_device(sd, probe, catalog_device)
        sd.save()

        for old_uuid in old_uuids:
            PhotoPath.objects.filter(filesystem_uuid=old_uuid).update(
                filesystem_uuid=new_uuid,
                storage_device=sd,
            )
            if not PhotoPath.objects.filter(filesystem_uuid=old_uuid).exists():
                StorageDevice.objects.filter(filesystem_uuid=old_uuid).delete()

        return sd


def ensure_storage_device_for_ingest(
    ingest_path: str,
    catalog_device: str,
    *,
    update_device: bool = False,
) -> Tuple[str, StorageDevice]:
    """Resolve volume identity and return ``(filesystem_uuid, StorageDevice)``.

    Runs a lightweight probe to determine ``filesystem_uuid``. Performs a deep
    probe when the volume is new or *update_device* is True.
    """
    light = probe_storage_from_path(ingest_path, deep=False)
    filesystem_uuid = resolve_volume_identity(light, catalog_device)

    if update_device:
        deep = probe_storage_from_path(ingest_path, deep=True)
        filesystem_uuid = resolve_volume_identity(deep, catalog_device)
        sd = migrate_volume_identity(catalog_device, deep, filesystem_uuid)
        return filesystem_uuid, sd

    existing = StorageDevice.objects.filter(filesystem_uuid=filesystem_uuid).first()
    if existing:
        if catalog_device and existing.catalog_device != catalog_device:
            existing.catalog_device = catalog_device
            existing.save(update_fields=["catalog_device"])
        return filesystem_uuid, existing

    deep = probe_storage_from_path(ingest_path, deep=True)
    filesystem_uuid = resolve_volume_identity(deep, catalog_device)

    device, _created = StorageDevice.objects.get_or_create(
        filesystem_uuid=filesystem_uuid,
        defaults={"catalog_device": catalog_device},
    )
    _merge_probe_into_device(device, deep, catalog_device)
    device.save()
    return filesystem_uuid, device
