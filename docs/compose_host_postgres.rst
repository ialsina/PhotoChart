Compose UI with host PostgreSQL
================================

This topology runs the PhotoChart UI, worker, Redis, and Nginx gateway in
Docker Compose while PostgreSQL and host ``pchart`` commands run directly on
the host.  Use it when you already maintain a local PostgreSQL server or want
host-native CLI commands and the Docker UI to share one catalog.

The default stack (``docker/compose.yaml`` with ``docker compose --project-directory .``)
is unchanged: it still starts the
bundled ``db`` service and stores PostgreSQL data in the ``postgres`` Docker
volume.  Host PostgreSQL is opt-in through ``docker/compose.host-postgres.yaml``.

Data flow
---------

.. code-block:: text

   host pchart / manage.py  --->  127.0.0.1:5432  --->  host PostgreSQL
   compose web / worker     --->  host.docker.internal:5432  ---^

   host pchart thumbnails   --->  PHOTOCHART_MEDIA_PATH
   compose web / gateway    --->  bind mount of the same directory

Prerequisites
-------------

#. Create one PostgreSQL role and database on the host.  The examples use
   ``photochart`` for both:

   .. code-block:: sql

      CREATE USER photochart WITH PASSWORD 'change-me';
      CREATE DATABASE photochart OWNER photochart;

#. Allow both local shell clients and Docker bridge clients to connect.  On
   Linux this usually means:

   * ``postgresql.conf``: set ``listen_addresses`` to include the Docker bridge
     interface, or use ``'*'`` on a trusted development machine.
   * ``pg_hba.conf``: allow ``photochart`` from ``127.0.0.1/32`` and from the
     Docker subnet used by the Compose network, for example ``172.16.0.0/12``
     for a broad local-development rule.

   Reload PostgreSQL after editing:

   .. code-block:: console

      sudo systemctl reload postgresql

   Keep these rules narrow on shared or production hosts.

#. Create one media directory that both host commands and containers will use:

   .. code-block:: console

      mkdir -p ./backend/media

Environment
-----------

Set the shared PostgreSQL credentials and media path in ``.env``:

.. code-block:: shell

   POSTGRES_DB=photochart
   POSTGRES_USER=photochart
   POSTGRES_PASSWORD=change-me
   POSTGRES_PORT=5432

   # Host CLI / manage.py connection.
   DATABASE_URL=postgresql://photochart:change-me@127.0.0.1:5432/photochart

   # Host path used by host ingest and bind-mounted into containers.
   MEDIA_ROOT=./backend/media
   PHOTOCHART_MEDIA_PATH=./backend/media

   # Opt in to the host-PostgreSQL Compose overlay.
   COMPOSE_FILE=docker/compose.yaml:docker/compose.host-postgres.yaml

``docker/compose.host-postgres.yaml`` points containers at
``host.docker.internal:5432``.  On Linux it also adds
``host.docker.internal:host-gateway`` to app containers.  Docker Desktop for
macOS and Windows provides that name automatically, but the explicit mapping is
harmless.

Start and initialize
--------------------

Run migrations once, either on the host:

.. code-block:: console

   python backend/manage.py migrate
   python backend/manage.py createsuperuser

or through Compose:

.. code-block:: console

   COMPOSE_FILE=docker/compose.yaml:docker/compose.host-postgres.yaml \
     docker compose --project-directory . up -d
   docker compose --project-directory . -f docker/compose.yaml \
     -f docker/compose.host-postgres.yaml exec web \
     python backend/manage.py createsuperuser

When this overlay is active, the bundled ``db`` service is assigned to the
``container-postgres`` profile and is not started by default.

Catalog with host pchart
------------------------

Host commands should use the same ``DATABASE_URL`` and ``MEDIA_ROOT`` as the
web app:

.. code-block:: console

   source .venv/bin/activate
   pchart ingest ./photos/Photos

If ``DATABASE_URL`` is set, Django ignores ``DATABASE_PATH``.  Do not mix this
topology with a SQLite catalog.

Verify the topology
-------------------

Check that host and container code see the same rows:

.. code-block:: console

   psql "$DATABASE_URL" -c 'select count(*) from photograph_photograph;'
   docker compose --project-directory . -f docker/compose.yaml \
     -f docker/compose.host-postgres.yaml exec web \
     python backend/manage.py shell -c \
     "from photograph.models import Photograph; print(Photograph.objects.count())"

Check which database URL the web container uses:

.. code-block:: console

   docker compose --project-directory . -f docker/compose.yaml \
     -f docker/compose.host-postgres.yaml exec web printenv DATABASE_URL

It should contain ``host.docker.internal``, not ``@db``.

Open ``http://localhost:${PHOTOCHART_PORT:-8080}``.  The Photographs tab first
shows year/month/day navigation; actual thumbnails load after drilling down to a
day or to ``Unknown``.

Troubleshooting
---------------

``UI is empty, host PostgreSQL has rows``
   The containers are probably still using the bundled ``db`` service.  Confirm
   ``docker compose --project-directory . -f docker/compose.yaml \
     -f docker/compose.host-postgres.yaml exec web printenv DATABASE_URL`` contains
   ``host.docker.internal`` and that ``COMPOSE_FILE`` includes
   ``docker/compose.host-postgres.yaml``.

``connection refused``
   PostgreSQL is not listening on an address reachable from the Docker bridge,
   or a firewall blocks port ``5432``.

``no pg_hba.conf entry``
   Add a ``pg_hba.conf`` rule for the Docker subnet.

``thumbnails are missing``
   Align ``MEDIA_ROOT`` for host commands with ``PHOTOCHART_MEDIA_PATH`` and
   restart the stack so app containers and the gateway use the same bind mount.

``migrate still waits for db``
   Recreate the services with the host-PostgreSQL overlay.  The migration job
   waits for the configured ``DATABASE_URL`` and no longer depends on the
   bundled ``db`` service.

Checking host connectivity
--------------------------

The helper below verifies that both the host and a Docker container can reach
the configured host PostgreSQL server:

.. code-block:: console

   scripts/check-host-postgres.sh

The script uses ``DATABASE_URL`` for host access and rewrites the hostname to
``host.docker.internal`` for the container-side probe.
