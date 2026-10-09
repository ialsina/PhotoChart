"""Resolve and persist :class:`StorageDevice` rows during ingest."""

from __future__ import annotations

from typing import Tuple

from django.utils import timezone

from photochart.fs.storage_probe import (
    StorageProbeResult,
    probe_storage_from_path,
    volume_filesystem_uuid,
)

from .models import StorageDevice


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
    filesystem_uuid = volume_filesystem_uuid(light, catalog_device)

    existing = StorageDevice.objects.filter(filesystem_uuid=filesystem_uuid).first()
    if existing and not update_device:
        if catalog_device and existing.catalog_device != catalog_device:
            existing.catalog_device = catalog_device
            existing.save(update_fields=["catalog_device"])
        return filesystem_uuid, existing

    deep = probe_storage_from_path(ingest_path, deep=True)
    filesystem_uuid = volume_filesystem_uuid(deep, catalog_device)

    device, created = StorageDevice.objects.get_or_create(
        filesystem_uuid=filesystem_uuid,
        defaults={"catalog_device": catalog_device},
    )
    _merge_probe_into_device(device, deep, catalog_device)
    device.save()
    return filesystem_uuid, device
