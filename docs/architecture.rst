Architecture
============

Separation of responsibilities
------------------------------

The organizer core under :mod:`photochart.organizer` does not depend on Django
or a specific storage provider. It coordinates domain policies through the
:class:`~photochart.organizer.storage.StorageAdapter` contract.

.. code-block:: text

   CLI / Django API / scheduler
                 |
                 v
          Organizer service
          |      |       |
          |      |       +-- collision, stability, retry policies
          |      +---------- metadata extraction and date resolution
          +----------------- StorageAdapter
                                |
             +------------------+------------------+
             |                  |                  |
       local/pCloud Drive   remote filesystems   object storage
                            and pCloud API            S3

The Django ``organizer`` app persists configuration without plaintext secrets,
jobs, individual operation results, and duplicate groups. The core can still be
used directly from the CLI without importing Django.

Processing lifecycle
--------------------

For every discovered object, the organizer:

#. filters unsupported extensions;
#. compares size and modification time over the stability interval;
#. extracts embedded image, RAW, or video metadata;
#. selects a plausible capture date and records its source;
#. renders the configured classification pattern;
#. creates the destination container;
#. resolves filename and content collisions;
#. copies or moves the object;
#. verifies the resulting object;
#. records success, duplicate, quarantine, skip, or failure.

Periodic polling is the correctness mechanism. A watch process repeatedly runs
the same idempotent one-shot scan, so a restart does not require reconstructing
filesystem watcher state.

Domain objects
--------------

:class:`~photochart.organizer.domain.MediaObject`
   Storage-independent object identity, path, name, size, modification time,
   content type, and provider metadata.

:class:`~photochart.organizer.domain.DateResult`
   Selected date, provenance, timezone, and confidence.

:class:`~photochart.organizer.domain.OperationResult`
   Final state, source, destination, metadata decision, details, and
   verification status.

:class:`~photochart.organizer.domain.StorageCapabilities`
   Explicit backend semantics such as atomic move, server-side move, random
   reads, resumable transfer, and object storage.

Safety model
------------

``move`` does not imply identical behavior on every backend:

* A local same-filesystem move can finish with an atomic rename.
* WebDAV, SFTP, and pCloud may provide a server-side move.
* S3 has no move operation; the adapter copies, verifies, and then deletes.
* A virtual drive can expose filesystem calls while retaining remote latency
  and failure behavior.

Adapters report these differences rather than presenting every backend as
POSIX. The source is removed only after destination verification. Unsupported
files remain untouched, and a processing error either leaves the source in
place or moves it to an explicitly configured quarantine.

Metadata architecture
---------------------

:class:`~photochart.organizer.metadata.MetadataExtractor` first uses ExifTool
when it is installed. Local files are inspected directly; remote objects are
downloaded to a temporary file that is removed afterward. PhotoChart's Pillow
metadata reader is the fallback. If no configured embedded field is plausible,
the object's modification time is used and marked as fallback provenance.

Database integration
--------------------

The core returns operation results. :mod:`backend.organizer.services` translates
them into ``OrganizerJob`` and ``OrganizerOperation`` records and, for local
successful files, invokes PhotoChart ingestion to update the photograph
catalog. This dependency points from Django integration to the core, never from
the core to Django.
