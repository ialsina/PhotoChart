Django and REST API
===================

Database models
---------------

``OrganizerConfiguration``
   Adapter, source, destination, pattern, mode, quarantine, and non-secret
   adapter options. Secret values are represented by ``*_env`` names.

``OrganizerJob``
   One execution attempt, its dry-run flag, lifecycle timestamps, state, and
   top-level error.

``OrganizerOperation``
   One source object result including destination, date provenance, detail, and
   verification status.

``DuplicateGroup``
   SHA-256 identity, object size, paths, and reclaimable bytes from a report.

``PlannedAction``
   Planner intent for delete, organize, or retry actions. Organizer jobs remain
   independently auditable.

API endpoints
-------------

All endpoints are rooted at ``/api/``.

============================================= ================================
Endpoint                                      Purpose
============================================= ================================
``organizer-health/``                         Readiness and adapter inventory
``organizer-configurations/``                 Configuration CRUD
``organizer-configurations/{id}/run/``        Start dry-run or real job
``organizer-jobs/``                           Job list and detail
``organizer-jobs/{id}/retry/``                Create a retry job
``organizer-operations/``                     Filterable operation audit
``duplicate-groups/``                         Duplicate report records
``duplicate-scans/``                          Duplicate scan status and provenance
``photographs/`` and ``photo-paths/``         Existing catalog API
``albums/``                                   Album management
``planned-actions/``                          Planner intents
============================================= ================================

Run request
-----------

.. code-block:: text

   POST /api/organizer-configurations/3/run/
   Content-Type: application/json

   {"dry_run": true}

The authenticated operator receives ``202 Accepted`` with a pending job.
Celery workers claim a database lease for the configuration, execute the scan,
and persist operations incrementally. The UI polls job summaries and fetches
paginated operation details separately. Retry jobs process only failed source
objects from the selected job; pending or running jobs can be cancelled.

All API routes require a Django session except liveness/readiness endpoints.
Real runs, retries, cancellation, planned actions, and configuration mutations
require the ``organizer.operate_organizer`` permission.

``POST /api/organizer-configurations/<id>/scan-duplicates/`` queues a
provider-backed duplicate scan and replaces that configuration's persisted
groups transactionally. Planned actions are also queued and retain
pending/running/completed/failed/cancelled state plus an idempotency key.
Remote organizer results explicitly report ``catalog_status=manual_required``;
filesystem-backed results are cataloged by the worker.

Operation filtering
-------------------

.. code-block:: text

   GET /api/organizer-operations/?job=12
   GET /api/organizer-operations/?status=failed
   GET /api/organizer-operations/?verified=true

Secret validation
-----------------

The configuration serializer rejects plaintext ``password``,
``access_token``, and ``secret_access_key`` keys. For example:

.. code-block:: json

   {
     "name": "Cloud inbox",
     "adapter": "pcloud_api",
     "source": "/PhotoUpload",
     "destination": "/Photos",
     "pattern": "%Y/%YQ%Q/%Y%M%D",
     "mode": "move",
     "adapter_options": {
       "access_token_env": "PCLOUD_ACCESS_TOKEN"
     }
   }

Frontend
--------

The React Organizer view lists configurations and recent jobs, launches dry-run
or real execution, and expands per-file operations. Provider secrets are never
returned because only environment-variable names are stored.

Migrations
----------

Apply schema changes before starting the API:

.. code-block:: console

   python backend/manage.py migrate
   python backend/manage.py makemigrations --check --dry-run
