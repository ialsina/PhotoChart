Command-line interface
======================

The installed executable is ``pchart``. In a source checkout,
``python -m cli.main`` invokes the same entry point.

Organization
------------

Start from an example in ``examples/organizer/`` (for example
``organizer.example.yaml``), copy it to a working file such as
``organizer.yaml``, and edit paths before running the commands below.

Preview one scan:

.. code-block:: console

   pchart organize once organizer.yaml --dry-run

Run one scan:

.. code-block:: console

   pchart organize once organizer.yaml

Poll continuously:

.. code-block:: console

   pchart organize watch organizer.yaml

``scan`` is a one-shot alias useful for discovery-oriented scripts. Common
overrides are:

``--copy`` / ``--move``
   Override configured transfer mode.

``--pattern PATTERN``
   Override the destination pattern.

``--dry-run``
   Resolve and print actions without changing storage.

Results are emitted one JSON object per line. This format can be redirected to
a log collector without parsing progress-oriented text.

Duplicate and missing-copy reports
----------------------------------

Report duplicate groups and reclaimable bytes:

.. code-block:: console

   pchart duplicates /data/Photos

Also report origin files for which no same-name, same-size destination
candidate exists:

.. code-block:: console

   pchart duplicates /media/card --missing-against /data/Photos

Duplicate groups use SHA-256 content checks after size grouping. Remote
duplicate reports can require full object reads and should be scheduled with
provider transfer costs in mind.

Metadata correction
-------------------

The command is non-mutating unless ``--apply`` is present:

.. code-block:: console

   pchart metadata-date IMG_1234.JPG 2026-09-28T14:23:18
   pchart metadata-date IMG_1234.JPG 2026-09-28T14:23:18 --apply

ExifTool retains its original-file backup by default. ``--no-backup`` disables
that safety mechanism. The command writes and verifies ``DateTimeOriginal`` and
``CreateDate`` for supported image and RAW formats.

Catalog ingestion
-----------------

.. code-block:: console

   pchart ingest /data/Photos

Important options include ``--no-checksum``, ``--no-recursive``,
``--no-store-images``, ``--resolution``, ``--log``, and ``--retry-thumbnails``.
Ingestion records files and thumbnails in Django but does not classify or move
the source.

``--retry-thumbnails`` scans the same file tree as a normal ingest but does not
add new catalog entries. It builds a work list of catalogued files (same stored
path and device label) whose photograph has no thumbnail; only those files are
processed and reflected in the progress bar. ``--no-store-images`` is ignored
in this mode.

Resize stored thumbnails
------------------------

Re-scale every photograph that already has a thumbnail in ``MEDIA_ROOT`` (the
command does not read original files from catalogued paths):

.. code-block:: console

   pchart resize-thumbnails --resolution medium
   pchart resize-thumbnails --resolution 800x600 --max-size 800K

``--resolution`` is required (preset name or ``WIDTHxHEIGHT``; see
``pchart list-resolutions``). ``--max-size`` is optional: thumbnails whose
stored file size is **below** the limit are left unchanged; only thumbnails at
or above the limit are resized.

Metadata inspection and conversion
----------------------------------

.. code-block:: console

   pchart info IMG_1234.NEF
   pchart convert IMG_1234.NEF --format JPEG --resolution 1080p
   pchart list-resolutions

Running CLI commands against removable or host paths
------------------------------------------------------

Most ``pchart`` commands work on any absolute path, but the default Docker
Compose stack only mounts ``/photos`` into ``web`` and ``worker``.  Use the
table below to choose the right invocation for each command and source type:

.. list-table:: Command execution matrix
   :header-rows: 1
   :widths: 20 20 30 30

   * - Command
     - Needs Django DB?
     - Path inside ``/photos``
     - Path on removable / host
   * - ``organize once/watch``
     - No
     - ``docker compose exec web pchart organize once …``
     - ``./scripts/compose-organize.sh SOURCE …``
       or host-native ``pchart organize once …``
   * - ``ingest``
     - Yes
     - ``docker compose exec web pchart ingest /photos/…``
       or ``./scripts/compose-ingest.sh /photos/…``
     - ``./scripts/compose-ingest.sh /mnt/camera/…``
   * - ``resize-thumbnails``
     - Yes
     - ``docker compose exec web pchart resize-thumbnails --resolution medium``
     - Host-native ``pchart resize-thumbnails …`` when Django DB and
       ``MEDIA_ROOT`` are configured locally
   * - ``duplicates``
     - No
     - ``docker compose exec web pchart duplicates /photos/…``
     - ``./scripts/compose-run.sh --from-path /mnt/… web pchart duplicates /mnt/…``
   * - ``metadata-date``
     - No
     - ``docker compose exec web pchart metadata-date /photos/… DATE``
     - ``./scripts/compose-run.sh --mount /mnt/…:/mnt/…:rw web pchart metadata-date …``
   * - ``info``
     - No
     - ``docker compose exec web pchart info /photos/IMG.NEF``
     - ``./scripts/compose-run.sh --from-path /mnt/… web pchart info /mnt/…/IMG.NEF``
   * - ``convert``
     - No
     - ``docker compose exec web pchart convert /photos/IMG.NEF --format JPEG``
     - ``./scripts/compose-run.sh --from-path /mnt/… web pchart convert /mnt/…/IMG.NEF …``

For the UI organizer (Photographs → Organizer tab) the source **must** be
inside ``/photos/…`` because it runs inside the long-lived Celery ``worker``.
Use the CLI scripts above for all removable-media or host-path workflows.

See :doc:`operations` for the full two-step organize → ingest playbook.

Exit status
-----------

``0``
   Command completed without failed operation results.

``1``
   Configuration, provider, processing, or report failure.

``2``
   Missing command/help invocation.

``130``
   Watch mode was interrupted from the terminal.
