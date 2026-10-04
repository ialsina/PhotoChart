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

   host pchart thumbnails   --->  MEDIA_ROOT (from .env)
   compose web / gateway    --->  bind mount of the same directory

Why two different hostnames?
----------------------------

Host ``pchart`` and ``manage.py`` should use ``127.0.0.1`` (or ``localhost``)
in ``DATABASE_URL``.  Processes inside Docker must use
``host.docker.internal`` instead: from a container, ``127.0.0.1`` is the
container itself, not your machine.

Containers reach the host through the Docker bridge.  On Linux,
``host.docker.internal`` usually resolves to ``172.17.0.1``, but PostgreSQL
sees the **client** as the container's address on that bridge (for example
``172.17.0.2``).  ``pg_hba.conf`` must allow that **source** subnet—not only
loopback.

PostgreSQL version on the host
------------------------------

Use any PostgreSQL version you already run on the host (for example 14).  The
bundled ``postgres:16`` image in ``docker/compose.yaml`` is only for the
default in-container ``db`` service; with this overlay that service is not
started.  PhotoChart connects to your host server over the normal client
protocol; you do not need to match the Compose image major version.

Prerequisites
-------------

#. Create one PostgreSQL role and database on the host.  The examples use
   ``photochart`` for both:

   .. code-block:: sql

      CREATE USER photochart WITH PASSWORD 'change-me';
      CREATE DATABASE photochart OWNER photochart;

#. Allow **both** host shell clients and Docker containers to authenticate.
   On Linux this usually requires two kinds of configuration:

   **Listen addresses** (``postgresql.conf``)

   PostgreSQL must accept TCP connections on an address reachable from Docker,
   not only on loopback.  For a trusted development machine, ``listen_addresses
   = '*'`` is common.  Confirm with:

   .. code-block:: console

      ss -tln | grep 5432

   You should see ``0.0.0.0:5432`` (or similar), not only ``127.0.0.1:5432``.

   **Client authentication** (``pg_hba.conf``)

   Rules for ``127.0.0.1/32`` cover host CLI access.  Containers need
   **separate** rules for the Docker address range, because connections arrive
   from IPs like ``172.17.0.2``.  Match the auth method already used for your
   TCP ``host`` lines (often ``scram-sha-256`` on PostgreSQL 14+).

   Example additions in ``pg_hba.conf`` (paths on Debian/Ubuntu are often under
   ``/etc/postgresql/<version>/main/``):

   .. code-block:: text

      # Host CLI
      host    photochart    photochart    127.0.0.1/32       scram-sha-256
      # Docker bridge and typical Compose networks (dev)
      host    photochart    photochart    172.17.0.0/16      scram-sha-256
      host    photochart    photochart    172.16.0.0/12      scram-sha-256

   Reload PostgreSQL after editing:

   .. code-block:: console

      sudo systemctl reload postgresql

   Keep these rules narrow on shared or production hosts.

#. Verify connectivity **before** starting Compose (see
   :ref:`compose-host-postgres-connectivity-check`).

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

or through Compose (single overlay file; it includes ``docker/compose.yaml``):

.. code-block:: console

   docker compose --project-directory . -f docker/compose.host-postgres.yaml up -d
   docker compose --project-directory . -f docker/compose.host-postgres.yaml exec web \
     python backend/manage.py createsuperuser

Alternatively, pass both Compose files explicitly:

.. code-block:: console

   COMPOSE_FILE=docker/compose.yaml:docker/compose.host-postgres.yaml \
     docker compose --project-directory . up -d

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

.. _compose-host-postgres-connectivity-check:

Checking host connectivity
--------------------------

Run this from the repository root with ``DATABASE_URL`` set in the environment
(load ``.env`` first if needed):

.. code-block:: console

   set -a && source .env && set +a
   scripts/check-host-postgres.sh

The script performs two checks:

#. **Host** — ``psql`` using ``DATABASE_URL`` (typically ``@127.0.0.1``).
#. **Container** — ``psql`` from a throwaway container via
   ``host.docker.internal``, the same path ``migrate`` and ``web`` use.

Both must succeed.  A lightweight probe such as ``pg_isready -h
host.docker.internal`` only confirms that something is listening; it does **not**
prove that ``pg_hba.conf`` allows user ``photochart``.  If the host step passes
and the container step fails with ``no pg_hba.conf entry for host "172.17.0.x"``,
add the Docker subnet rules in ``pg_hba.conf`` above and reload PostgreSQL.

Optional manual container probe (client tools only; does not start a database
server on your machine):

.. code-block:: console

   docker run --rm --add-host=host.docker.internal:host-gateway postgres:16-alpine \
     pg_isready -h host.docker.internal -p 5432

Use ``scripts/check-host-postgres.sh`` for the full login test.

Verify the topology
-------------------

Check that host and container code see the same rows:

.. code-block:: console

   psql "$DATABASE_URL" -c 'select count(*) from photograph_photograph;'
   docker compose --project-directory . -f docker/compose.host-postgres.yaml exec web \
     python backend/manage.py shell -c \
     "from photograph.models import Photograph; print(Photograph.objects.count())"

Check which database URL the web container uses:

.. code-block:: console

   docker compose --project-directory . -f docker/compose.host-postgres.yaml exec web \
     printenv DATABASE_URL

It should contain ``host.docker.internal``, not ``@db``.

Open ``http://localhost:${PHOTOCHART_PORT:-8080}``.  The Photographs tab first
shows year/month/day navigation; actual thumbnails load after drilling down to a
day or to ``Unknown``.

Troubleshooting
---------------

``UI is empty, host PostgreSQL has rows``
   The containers are probably still using the bundled ``db`` service.  Run
   ``docker compose --project-directory . -f docker/compose.host-postgres.yaml exec web printenv DATABASE_URL``
   and confirm the output contains ``host.docker.internal`` and that
   ``COMPOSE_FILE`` includes ``docker/compose.host-postgres.yaml``.

``connection refused`` (often from ``wait_for_database`` / ``migrate``)
   PostgreSQL is not listening on an address reachable from the Docker bridge,
   or a firewall blocks port ``5432``.  On the host, compare
   ``pg_isready -h 127.0.0.1 -p 5432`` with
   ``pg_isready -h 172.17.0.1 -p 5432``.  If loopback works but the bridge
   gateway does not, fix ``listen_addresses``.  If both work on the host but
   containers still fail, check UFW or ``iptables`` rules that block
   container-to-host traffic on port ``5432``.

``no pg_hba.conf entry for host "172.17.0.x"`` (``check-host-postgres.sh`` or ``migrate``)
   TCP connectivity is fine but PostgreSQL rejects the login.  The IP in the
   message is the **container's** address, not ``host.docker.internal``
   (``172.17.0.1``).  Add ``host`` lines for ``172.17.0.0/16`` and/or
   ``172.16.0.0/12`` for user and database ``photochart``, using the same
   auth method as your ``127.0.0.1`` rule, then ``sudo systemctl reload
   postgresql``.  Re-run ``scripts/check-host-postgres.sh`` until both steps
   pass.

``pg_isready`` from a container works but ``check-host-postgres.sh`` fails
   Expected: ``pg_isready`` does not authenticate as ``photochart``.  Fix
   ``pg_hba.conf`` as above; rely on the script, not ``pg_isready`` alone.

``thumbnails are missing`` or ``/media/...`` returns **404**
   Host ingest must write thumbnails under the ``MEDIA_ROOT`` path from ``.env``.
   The overlay bind-mounts that directory into ``web`` and ``gateway`` (nginx
   serves files via ``X-Accel-Redirect``).  If ``PHOTOCHART_MEDIA_PATH`` still
   points at a different folder, remove it or set it equal to ``MEDIA_ROOT``,
   then recreate the stack:

   .. code-block:: console

      docker compose --project-directory . -f docker/compose.host-postgres.yaml up -d --force-recreate web gateway

``migrate`` / ``photochart-migrate-1`` did not complete successfully
   After ``scripts/check-host-postgres.sh`` passes, recreate the one-shot migrate
   job:

   .. code-block:: console

      docker compose --project-directory . -f docker/compose.host-postgres.yaml up -d --force-recreate

   If ``wait_for_database`` still fails, inspect
   ``docker compose --project-directory . -f docker/compose.host-postgres.yaml logs migrate``.
   If it prints ``Database is available`` and then errors, the problem is the
   migration itself (permissions, schema), not network access.
