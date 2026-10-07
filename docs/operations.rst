Operations and recovery
=======================

Operation states
----------------

``discovered``
   Object is visible but not yet processed.

``skipped``
   Unsupported processing window, active lock, or unstable object.

``dry_run``
   Destination and policy were resolved without mutation.

``copied`` / ``moved``
   Transfer completed and destination verification passed.

``duplicate``
   Identical content already exists at a resolved destination.

``quarantined``
   Processing failed and configured quarantine received the source.

``failed``
   Retries were exhausted or a permanent/configuration error occurred.

Collision handling
------------------

The organizer first checks destination existence, then size, then content. An
identical destination is idempotent. With move mode, an identical verified
source can be removed because the destination already holds the content. With
suffix mode, different content becomes ``name_1.ext``, ``name_2.ext``, and so
on.

Quarantine
----------

Quarantine paths are grouped by processing date. A quarantined file is not
silently deleted and its operation retains the reason. Operators should inspect
metadata, permissions, and collision details before retrying or restoring it.

Failure classification
----------------------

Transient examples include provider unavailability, timeouts, and temporary
I/O errors. These receive bounded retry. Permanent examples include unsupported
media or invalid metadata. Conflict examples include an occupied destination
under a fail policy. Configuration failures include invalid patterns, missing
paths, and absent credentials.

Monitoring
----------

Use:

* ``/livez`` for web-process liveness;
* ``/readyz`` for database, Redis, and worker readiness;
* token-protected ``/metrics`` for job and failure gauges;
* ``/api/organizer-jobs/`` for job state;
* ``/api/organizer-operations/?job=ID`` for per-object audit;
* structured JSON application logs correlated by ``X-Request-ID``.

A job can complete with skipped or duplicate objects. Failed object results
make the persisted job fail. API retry creates a new job, preserving the
previous attempt for audit.

Backup and recovery
-------------------

The organizer is not a backup system. Before move mode:

#. maintain an independent backup;
#. test database restore and provider object recovery;
#. retain object versions where the provider supports them;
#. verify quarantine and temporary-file cleanup;
#. retain organizer operations long enough for incident investigation.

Create an encrypted/off-host production backup with:

.. code-block:: console

   scripts/backup-production.sh /secure/off-host/photochart-$(date +%F)

The backup contains a PostgreSQL custom-format dump, media archive, deployment
configuration, environment file, and checksums. The environment file contains
secrets; preserve mode ``0600`` and encrypt it at rest.

Restore only into a prepared maintenance window:

.. code-block:: console

   scripts/restore-production.sh --confirm /secure/off-host/photochart-2026-09-30

The restore script verifies checksums, stops mutating services, restores the
database and media volume, applies migrations, and restarts the stack. After
every restore, verify ``/readyz``, inspect failed/stale jobs, run catalog
reconciliation, and execute a dry-run against representative sources. Record a
successful restore drill before each production release.

If processing stops mid-copy, the source remains and local/SFTP partial objects
use a ``.partial`` suffix. The next reconciliation scan sees the source again.
S3 source deletion occurs only after verified copy.

Performance
-----------

Hashing and metadata extraction may download complete remote objects. Start
with one worker. Size checks avoid unnecessary hashing for most collisions, but
duplicate reports intentionally read same-size candidates. Schedule large
remote reports away from provider rate or bandwidth limits.

Legacy systemd example
----------------------

One-shot timer service:

.. code-block:: ini

   [Unit]
   Description=PhotoChart organizer scan
   After=network-online.target

   [Service]
   Type=oneshot
   User=photochart
   WorkingDirectory=/opt/photochart
   EnvironmentFile=/etc/photochart/photochart.env
   ExecStart=/opt/photochart/.venv/bin/pchart organize once /etc/photochart/organizer.yaml

Pair it with a timer:

.. code-block:: ini

   [Timer]
   OnBootSec=2m
   OnUnitActiveSec=1m
   Persistent=true

   [Install]
   WantedBy=timers.target

Cron alternative
----------------

.. code-block:: text

   * * * * * cd /opt/photochart && .venv/bin/pchart organize once /etc/photochart/organizer.yaml

The supported production stack uses Celery and database leases. Do not run
these legacy schedulers alongside the Compose worker, cron, or watch mode
against the same source.

.. _operations:Removable media and host paths:

Removable media and host paths
------------------------------

The default Compose stack mounts only ``${PHOTO_LIBRARY_PATH}`` (→ ``/photos``)
into ``web`` and ``worker``.  USB drives, SD cards, and other host volumes are
not visible inside those containers.

The recommended two-step workflow for any external device is:

1. **Organize** – copy/move files from the device into the shared library.
2. **Catalog** – ingest the library into the database.

There are two tracks depending on whether you want to run Python on the host or
keep everything inside Docker.

.. code-block:: text

   USB/SD card  ──organize──▶  ./photos/Photos  ──ingest──▶  Postgres catalog
   (host mount)                 (Compose bind)                (Photographs UI)

Track 1 – Compose scripts (no host Python required)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

All three scripts call ``docker compose run --rm --no-deps`` internally (via
``scripts/lib/compose.sh``, which passes ``--project-directory`` and
``-f docker/compose.yaml``) and
share path-validation logic from ``scripts/lib/mounts.sh``.

**Step 1 – Organize into the library**

.. code-block:: console

   # Preview (no files moved):
   ./scripts/compose-organize.sh /run/media/$USER/EOS_DIGITAL/DCIM --dry-run

   # Copy files (source intact):
   ./scripts/compose-organize.sh /run/media/$USER/EOS_DIGITAL/DCIM --copy

   # Move files (removes source after verified copy – use with caution):
   ./scripts/compose-organize.sh /run/media/$USER/EOS_DIGITAL/DCIM --move

The script generates a minimal organizer YAML on the fly, bind-mounts the
device's filesystem root read-only (or read-write for ``--move``), and runs
``pchart organize once`` in a one-shot container.  Files land in
``/photos/Photos`` (configurable via ``PHOTO_DEST_PATH``).

**Step 2 – Catalog the library**

.. code-block:: console

   ./scripts/compose-ingest.sh /photos/Photos

``scripts/compose-ingest.sh`` is a convenience wrapper for the common case
where you want to ingest a path that is not permanently mounted:

.. code-block:: console

   ./scripts/compose-ingest.sh /mnt/camera/DCIM
   ./scripts/compose-ingest.sh /run/media/$USER/SD_CARD --no-store-images
   ./scripts/compose-ingest.sh /mnt/camera/DCIM --raw

**Generic runner for other commands**

``scripts/compose-run.sh`` adds extra binds for *any* ``pchart`` command:

.. code-block:: console

   # Duplicate report: USB card vs library
   ./scripts/compose-run.sh \
     --from-path /run/media/$USER/EOS_DIGITAL/DCIM \
     web pchart duplicates /run/media/$USER/EOS_DIGITAL/DCIM \
     --missing-against /photos/Photos

   # EXIF date correction (needs write access to card):
   ./scripts/compose-run.sh \
     --mount /run/media/$USER/SD_CARD:/run/media/$USER/SD_CARD:rw \
     web pchart metadata-date /run/media/$USER/SD_CARD/IMG.JPG \
     "2026-01-01T12:00:00" --apply

   # File info from any host path:
   ./scripts/compose-run.sh \
     --from-path /mnt/archive \
     web pchart info /mnt/archive/IMG_1234.NEF

``--from-path PATH`` auto-detects the device mount root and adds a read-only
bind.  ``--mount SRC[:DST[:MODE]]`` allows explicit control.

Track 2 – Host-native (pchart installed on the host)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If ``pchart`` is installed in a host virtualenv, you can run organize and most
CLI commands entirely on the host without any Docker interaction:

.. code-block:: console

   # Edit examples/organizer/organizer.removable-inbox.example.yaml, then:
   pchart organize once examples/organizer/organizer.removable-inbox.example.yaml --dry-run
   pchart organize once examples/organizer/organizer.removable-inbox.example.yaml --copy

   # Catalog the library through the same PostgreSQL server the UI uses:
   DATABASE_URL=postgresql://photochart:photochart@127.0.0.1:5432/photochart \
     MEDIA_ROOT=./backend/media \
     pchart ingest ./photos/Photos

See ``examples/organizer/organizer.removable-inbox.example.yaml`` for a
fully-annotated host-path configuration.

There are two supported ways for host ``pchart`` and the Compose UI to share a
catalog:

* **Bundled PostgreSQL** (default ``docker/compose.yaml``): publish the ``db`` service
  to a host port, then point host ``DATABASE_URL`` at that published port.  The
  UI still uses ``db:5432`` inside Docker.
* **Host PostgreSQL**: set
  ``COMPOSE_FILE=docker/compose.yaml:docker/compose.host-postgres.yaml`` and point host
  ``DATABASE_URL`` at ``127.0.0.1:5432``.  Containers use
  ``host.docker.internal:5432``.  Configure ``pg_hba.conf`` for Docker client
  subnets (not only ``127.0.0.1``), then run ``scripts/check-host-postgres.sh``
  before ``docker compose up``.  See :doc:`compose_host_postgres`.

Do not mix these: host PostgreSQL on ``127.0.0.1:5432`` and the bundled
Compose ``db`` service are separate PostgreSQL servers unless all clients are
intentionally pointed at one of them.

.. note::
   Do **not** run a host ``pchart organize watch`` and the Compose **worker**
   organizer against the **same source** simultaneously.  Use one or the other.

**UI organizer (OrganizerConfiguration) – library paths only**

The Photographs → Organizer tab creates jobs that run inside the Celery
``worker`` container.  Source and destination paths must be visible to the
worker (i.e. under ``/photos/...`` in the default Compose setup).  For
removable-media inboxes use the CLI scripts above; the UI organizer supports
library-internal reorganisation only.

.. note::
   Files on the host that are not permanently bind-mounted will not be served
   as originals through the UI after the one-shot container exits.  Set
   ``store_images: true`` (the default) to copy thumbnails into the ``media``
   volume so the Photographs grid works even when the device is disconnected.

**Catalog ingestion via API / Celery**

Operators can POST to ``/api/ingest-jobs/`` to queue a job:

.. code-block:: console

   # Library path (already visible in the worker):
   curl -X POST /api/ingest-jobs/ \
     -H "Content-Type: application/json" \
     -d '{"path": "/photos/Photos"}'

   # External path (requires INGEST_DOCKER_ENABLED=true in .env):
   curl -X POST /api/ingest-jobs/ \
     -H "Content-Type: application/json" \
     -d '{"path": "/mnt/camera/DCIM",
          "mount_root": "/mnt/camera",
          "device": "EOS_DIGITAL (/mnt/camera)"}'

   # RAW files only (skip in-camera JPEGs in the same tree):
   curl -X POST /api/ingest-jobs/ \
     -H "Content-Type: application/json" \
     -d '{"path": "/mnt/camera/DCIM", "raw_only": true}'

When ``INGEST_DOCKER_ENABLED=true``, the Celery worker spawns the same one-shot
container pattern used by ``scripts/compose-ingest.sh``.  This requires:

1. ``/var/run/docker.sock`` mounted into the ``worker`` service (see
   ``compose.override.yaml`` example in ``docs/deployment.rst``).
2. ``INGEST_ALLOWED_PATH_PREFIXES`` set to the host roots the worker is allowed
   to bind-mount (e.g. ``INGEST_ALLOWED_PATH_PREFIXES=/mnt,/media``).
3. ``INGEST_ALWAYS_ALLOWED_PREFIXES`` (default ``/photos``) ensures library
   paths always pass validation even when external prefixes are configured.

**Device labels and reconnecting**

``PhotoPath.device`` stores the label produced at ingest time.  For a USB drive
ingested as ``"EOS_DIGITAL (/mnt/camera)"``, the Photo Paths tab will show that
device name.  If you plug the same drive in later at a different mount point,
run ingest again with the same ``--device`` value to link new shots to the
same device in the catalog.
