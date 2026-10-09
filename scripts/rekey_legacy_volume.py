#!/usr/bin/env python3
"""Re-key migrated legacy PhotoPath volumes to probed FUSE/block UUIDs.

After migration 0014, existing paths use ``photchart:legacy:…`` while live
ingest on FUSE mounts (e.g. pCloud Drive) uses ``photchart:fuse:…``.  A mistaken
full re-ingest can duplicate the catalog.  This script:

1. Probes *mount* and computes the canonical ``filesystem_uuid`` (same as ingest).
2. Deletes ``PhotoPath`` rows already using that UUID (duplicate ingest from the
   mistaken re-ingest). Legacy rows still use ``photchart:legacy:…`` until step 3.
3. Re-keys legacy paths for *device_label* to the probed UUID and updates
   ``StorageDevice`` metadata.

Other volumes (other fuse UUIDs or device labels) are not touched.

For USB/block volumes with ``photchart:legacy:…`` rows, prefer
``pchart ingest <mount> --update-device`` after upgrading PhotoChart (uses
partition UUID and parent-disk serial metadata).

Default is dry-run (transaction rolled back).  Pass ``--doit`` to persist.

Example::

    python scripts/rekey_legacy_volume.py \\
        --mount ~/pCloudDrive \\
        --device-label 'pCloudDrive (/home/you/pCloudDrive)'

    python scripts/rekey_legacy_volume.py --mount ~/pCloudDrive \\
        --device-label 'pCloudDrive (/home/you/pCloudDrive)' --doit
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def _setup_django() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
    import django

    django.setup()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Remove duplicate PhotoPath rows for the probed volume UUID, then "
            "re-key photchart:legacy paths for --device-label to that UUID."
        ),
    )
    parser.add_argument(
        "--mount",
        type=Path,
        required=True,
        help="Mounted volume root to probe (e.g. ~/pCloudDrive).",
    )
    parser.add_argument(
        "--device-label",
        type=str,
        required=True,
        help="Exact PhotoPath.device string for legacy rows to re-key.",
    )
    parser.add_argument(
        "--legacy-uuid",
        type=str,
        default=None,
        help="Override legacy filesystem_uuid (default: hash of --device-label).",
    )
    parser.add_argument(
        "--doit",
        action="store_true",
        help="Apply changes. Without this flag, only print the plan and roll back.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    mount = args.mount.expanduser().resolve()
    if not mount.exists():
        print(f"ERROR: mount path does not exist: {mount}", file=sys.stderr)
        return 1

    _setup_django()

    from django.db import transaction
    from django.utils import timezone

    from photochart.fs.storage_probe import (
        legacy_filesystem_uuid,
        probe_storage_from_path,
        volume_filesystem_uuid,
    )
    from photograph.models import PhotoPath, StorageDevice

    legacy_uuid = args.legacy_uuid or legacy_filesystem_uuid(args.device_label)

    probe = probe_storage_from_path(str(mount), deep=True)
    target_uuid = volume_filesystem_uuid(probe, args.device_label)

    # Duplicate ingest rows already sit on target_uuid; legacy rows still on legacy_uuid.
    duplicate_path_qs = PhotoPath.objects.filter(filesystem_uuid=target_uuid)
    legacy_path_qs = PhotoPath.objects.filter(filesystem_uuid=legacy_uuid)
    legacy_by_label = PhotoPath.objects.filter(device=args.device_label)
    other_fuse_count = (
        PhotoPath.objects.filter(filesystem_uuid__startswith="photchart:fuse:")
        .exclude(filesystem_uuid=target_uuid)
        .count()
    )

    print("=== Plan ===")
    print(f"Mount:           {mount}")
    print(f"Device label:    {args.device_label}")
    print(f"Legacy UUID:     {legacy_uuid}")
    print(f"Target UUID:     {target_uuid}")
    print(f"Probe mount:     {probe.mount_root}")
    print(f"Probe fstype:    {probe.fstype}")
    print(f"Probe source:    {probe.source}")
    print(f"Probe notes:     {probe.notes}")
    print()
    print(
        f"PhotoPath rows to DELETE (duplicate ingest, uuid={target_uuid[:48]}…): "
        f"{duplicate_path_qs.count()}"
    )
    print(f"PhotoPath rows to RE-KEY (legacy uuid):      {legacy_path_qs.count()}")
    print(f"PhotoPath rows with device label:            {legacy_by_label.count()}")
    if other_fuse_count:
        print(
            f"Other photchart:fuse paths (NOT deleted):    {other_fuse_count}",
        )
    if legacy_path_qs.count() != legacy_by_label.count():
        print(
            "WARNING: legacy uuid count != device label count; "
            "verify --device-label / --legacy-uuid.",
            file=sys.stderr,
        )

    if target_uuid == legacy_uuid:
        print(
            "WARNING: target UUID equals legacy UUID; re-key would be a no-op.",
            file=sys.stderr,
        )

    if not args.doit:
        print()
        print("Dry run only (no --doit). Re-run with --doit to apply.")

    try:
        with transaction.atomic():
            deleted_paths, path_del_detail = duplicate_path_qs.delete()
            deleted_sd, sd_del_detail = StorageDevice.objects.filter(
                filesystem_uuid=target_uuid
            ).delete()

            sd, _created = StorageDevice.objects.update_or_create(
                filesystem_uuid=target_uuid,
                defaults={
                    "catalog_device": args.device_label,
                    "capacity_bytes": probe.capacity_bytes,
                    "source": probe.source,
                    "fstype": probe.fstype,
                    "mount_root": probe.mount_root,
                    "probe_notes": probe.notes or "rekey_script",
                    "probed_at": timezone.now(),
                },
            )

            updated = legacy_path_qs.update(
                filesystem_uuid=target_uuid,
                storage_device=sd,
            )

            removed_legacy_sd, _ = StorageDevice.objects.filter(
                filesystem_uuid=legacy_uuid
            ).delete()

            print()
            print("=== Applied (in transaction) ===")
            print(
                f"Deleted PhotoPath-related objects: {deleted_paths} ({path_del_detail})"
            )
            print(f"Deleted target StorageDevice rows: {deleted_sd} ({sd_del_detail})")
            print(f"Re-keyed PhotoPath rows:           {updated}")
            print(f"Removed legacy StorageDevice rows: {removed_legacy_sd}")
            print(f"StorageDevice id for target UUID:  {sd.pk}")

            if not args.doit:
                print()
                print("Rolling back (dry run).")
                raise _DryRunRollback()

    except _DryRunRollback:
        return 0

    print()
    print("Done. Next ingest on this mount should skip already-catalogued paths.")
    return 0


class _DryRunRollback(Exception):
    """Rollback atomic block after printing dry-run results."""


if __name__ == "__main__":
    raise SystemExit(main())
