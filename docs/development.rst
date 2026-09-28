Development
===========

Repository layout
-----------------

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

   python -m pytest tests --no-cov
   python backend/manage.py test organizer
   python backend/manage.py check
   npm --prefix frontend run build

The project-wide pytest configuration enforces coverage when ``--no-cov`` is
not supplied. Use focused tests during development, then run the configured
coverage suite before release.

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
