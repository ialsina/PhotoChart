Command-line interface
======================

The installed executable is ``pchart``. In a source checkout,
``python -m cli.main`` invokes the same entry point.

Organization
------------

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
``--no-store-images``, ``--resolution``, and ``--log``. Ingestion records files
and thumbnails in Django but does not classify or move the source.

Metadata inspection and conversion
----------------------------------

.. code-block:: console

   pchart info IMG_1234.NEF
   pchart convert IMG_1234.NEF --format JPEG --resolution 1080p
   pchart list-resolutions

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
