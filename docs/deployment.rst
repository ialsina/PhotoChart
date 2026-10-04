Deployment and security
=======================

Production environment
----------------------

At minimum configure:

.. code-block:: shell

   DEBUG=false
   SECRET_KEY=a-long-random-secret
   ALLOWED_HOSTS=photos.example.test
   CORS_ALLOWED_ORIGINS=https://photos.example.test
   CSRF_TRUSTED_ORIGINS=https://photos.example.test
   SECURE_SSL_REDIRECT=true
   SECURE_HSTS_SECONDS=31536000
   DATABASE_URL=postgresql://photochart:password@db/photochart
   CELERY_BROKER_URL=redis://redis:6379/0
   METRICS_TOKEN=a-separate-random-monitoring-token

Terminate TLS at a trusted reverse proxy, forward the correct scheme, and
restrict the admin site at the network layer. The API uses same-origin Django
sessions and CSRF protection. Grant ``organizer.operate_organizer`` only to
trusted operators.

Filesystem permissions
----------------------

Run as a dedicated user with:

* read/write access only to configured inbox, destination, quarantine, and
  media paths;
* read-only access to configuration;
* no shell-readable provider secrets outside its environment file;
* a private SFTP key and verified known-hosts file.

Do not run the organizer as root.

Database
--------

SQLite is development-only. Production requires PostgreSQL so job leases,
workers, API requests, and audit writes share transactional state. Back up the
database before migrations and test restoration of operation history.

Provider credentials
--------------------

Use environment files with mode ``0600`` or a service secret manager. Never
place access tokens or passwords in YAML committed to source control. Rotate
credentials after suspected log or host exposure.

pCloud Drive startup
--------------------

Order the organizer after the pCloud mount and network are ready. The adapter
health check distinguishes an unavailable mount from an empty inbox. Test
whether rename causes a remote server-side move for the deployed client
version.

Containers
----------

The supported production topology is defined by ``compose.yaml``:
PostgreSQL, Redis, a migration job, Gunicorn, Celery worker and beat, and an
Nginx gateway. Start it only after creating a mode-``0600`` ``.env`` from
``.env.example`` and mounting the intended photo library:

.. code-block:: console

   docker compose build
   docker compose up -d
   docker compose exec web python backend/manage.py createsuperuser

Compose defaults ``CSRF_TRUSTED_ORIGINS`` from ``PHOTOCHART_PORT`` and disables
secure session/CSRF cookies for local HTTP login. Behind HTTPS in production,
set ``SESSION_COOKIE_SECURE=true``, ``CSRF_COOKIE_SECURE=true``, and
``CSRF_TRUSTED_ORIGINS`` to your public origin(s) in ``.env``.

Mount source, destination, quarantine, and media explicitly. A container using
pCloud Drive generally needs the host mount passed through; API/WebDAV/SFTP/S3
adapters do not require a virtual filesystem.

To ingest from removable media (USB drives, SD cards) without restarting the
stack, use ``scripts/compose-ingest.sh`` (see "Ingest from removable media" in
``docs/operations.rst``).  If you want the Celery worker to spawn ingest
containers automatically, add a ``compose.override.yaml``:

.. code-block:: yaml

   # compose.override.yaml – enables API-driven Docker ingest
   # WARNING: mounting the Docker socket grants the worker effective root access
   #          to the host.  Use only in trusted environments.
   services:
     worker:
       volumes:
         - /var/run/docker.sock:/var/run/docker.sock
       environment:
         INGEST_DOCKER_ENABLED: "true"
         INGEST_ALLOWED_PATH_PREFIXES: "/mnt,/media,/run/media"
         COMPOSE_PROJECT_NAME: photochart

ExifTool must be installed in the runtime image for comprehensive metadata.
Install only optional Python extras needed by enabled providers.

``/livez`` checks only the web process. ``/readyz`` requires PostgreSQL, Redis,
and a recent Celery worker heartbeat. ``/metrics`` requires the configured
bearer token and reports job and failed-operation gauges. Alert on readiness
failure, stale/running jobs, failed operations, and transfer verification
errors. Media responses are session-authorized by Django and delivered through
Nginx's internal ``X-Accel-Redirect`` location.

Release checklist
-----------------

#. ``make verify``
#. ``make check-deploy``
#. ``make package``
#. ``docker compose build``
#. ``make linkcheck``
#. backup database and configuration;
#. migrate;
#. run provider dry-run acceptance tests;
#. deploy with move mode disabled initially.

Versioned releases
------------------

Release versions come from annotated git tags matching ``v*`` (for example
``v0.3.0``), via ``setuptools-scm``. Before tagging, replace
``[Unreleased]`` with ``[vX.Y.Z]`` and the release date, then run:

.. code-block:: console

   scripts/check-release.py --tag vX.Y.Z
   make verify check-deploy package

Pushing the matching tag builds distributions and both container targets,
repeats all release gates, and creates the GitHub release. Perform and record a
successful backup/restore drill before pushing the tag.

Container images are built without ``.git`` in the build context. Pass the
release version explicitly, for example
``docker build --build-arg SETUPTOOLS_SCM_PRETEND_VERSION=0.3.0 ...`` (the
release workflow does this from the tag name).
