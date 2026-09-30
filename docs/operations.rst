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
