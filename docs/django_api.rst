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

The response is the created job with nested operations. Execution is currently
synchronous: the HTTP request remains open while the scan runs. For long remote
jobs, invoke the core CLI through a scheduler or place ``execute_job`` behind a
deployment-specific worker queue.

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
