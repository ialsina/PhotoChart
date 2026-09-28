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
   DATABASE_URL=postgresql://photochart:password@db/photochart

Terminate TLS at a trusted reverse proxy, forward the correct scheme, and
restrict the API and admin site with deployment-appropriate authentication.
The current development settings do not by themselves provide a public
multi-user authorization model.

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

SQLite is suitable for a single process and small installation. PostgreSQL is
recommended when the API, scheduler, or workers can overlap. Back up the
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

Mount source, destination, quarantine, and media explicitly. A container using
pCloud Drive generally needs the host mount passed through; API/WebDAV/SFTP/S3
adapters do not require a virtual filesystem.

ExifTool must be installed in the runtime image for comprehensive metadata.
Install only optional Python extras needed by enabled providers.

Release checklist
-----------------

#. ``python -m pytest tests --no-cov``
#. ``python backend/manage.py test organizer``
#. ``python backend/manage.py check --deploy``
#. ``python backend/manage.py makemigrations --check --dry-run``
#. ``npm --prefix frontend run build``
#. ``make html``
#. ``make linkcheck``
#. backup database and configuration;
#. migrate;
#. run provider dry-run acceptance tests;
#. deploy with move mode disabled initially.
