Development
===========

Repository layout
-----------------

``photochart/common/``
   Shared utilities (logging).

``photochart/fs/``
   File operations (checksums, copy/move) and Linux mount/device helpers.

``photochart/media/``
   Supported extensions and resolution presets.

``photochart/imaging/``
   Image backends, conversion, EXIF helpers, and full metadata extraction
   (:mod:`photochart.imaging.extract`).

``photochart/ingest/``
   Catalog ingestion (:mod:`photochart.ingest.photos`) and host/Docker
   orchestration (:mod:`photochart.ingest.runner`).

``photochart/organizer/``
   Provider-independent domain, configuration, patterns, policies, metadata,
   reports, service, and adapter contract.

``photochart/organizer/adapters/``
   Local, pCloud, WebDAV/Nextcloud, SFTP, and S3 implementations.

``cli/``
   Command parsing and command handlers. Django initializes lazily only for
   database-backed commands.

``backend/``
   Django catalog, albums, planner, organizer jobs, REST API, and migrations.

``frontend/``
   React/Vite browser interface.

``tests/``
   Core and adapter unit tests. Credentialed provider acceptance tests should
   use isolated test prefixes and remain opt-in.

Testing
-------

.. code-block:: console

   make verify
   make check-deploy
   make package

``make verify`` mirrors the pull-request checks: risk-focused Python coverage,
all Django tests, migration drift, frontend lint and build, and strict HTML
documentation. Use ``make test`` for a fast Python-only development cycle.

Adding an adapter
-----------------

#. Implement :class:`photochart.organizer.storage.StorageAdapter`.
#. Return stable provider object IDs where possible.
#. Map not-found separately from authentication and transient failures.
#. Report capabilities truthfully.
#. Never delete a source before verified destination creation.
#. Add the adapter to ``build_adapter`` without importing its optional SDK at
   module import time.
#. Add fake-client unit tests and credentialed acceptance tests.
#. Document options, secret handling, semantics, and provider limitations.

Adapter methods should not translate every provider failure into ``False``.
For example, ``exists`` returns ``False`` only for a confirmed not-found
response; backend unavailability must propagate.

Adding metadata fields
----------------------

Update the configured priority rather than hard-coding provider-specific date
selection. Parsing belongs in :mod:`photochart.organizer.metadata`; storage
adapters only make bytes available.

Database changes
----------------

.. code-block:: console

   python backend/manage.py makemigrations
   python backend/manage.py migrate
   python backend/manage.py makemigrations --check --dry-run

Keep core objects independent from Django models. Translate domain results in
``backend/organizer/services.py``.

Documentation
-------------

.. code-block:: console

   pip install -e ".[docs]"
   make html
   make linkcheck
   make pdf-latex

HTML is written to ``docs/_build/html``. LaTeX sources are written to
``docs/_build/latex`` and the PDF target places ``PhotoChart.pdf`` there.
