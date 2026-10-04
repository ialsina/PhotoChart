Configuration
=============

Organizer YAML
--------------

The complete local example is:

.. literalinclude:: ../organizer.example.yaml
   :language: yaml

Source and destination
----------------------

``source.path``
   Inbox or prefix scanned recursively.

``destination.path``
   Root under which rendered classification paths are created.

``destination.pattern``
   Relative path template. Absolute paths and ``..`` traversal are rejected.

Pattern language
----------------

Patterns use organizer-specific tokens rather than :func:`datetime.strftime`.

====== ================== ========
Token  Meaning            Example
====== ================== ========
``%Y`` four-digit year    ``2026``
``%M`` two-digit month    ``09``
``%D`` two-digit day      ``28``
``%Q`` quarter number     ``3``
``%%`` literal percent    ``%``
====== ================== ========

Examples:

``%YQ%Q/%Y%M%D``
   Produces ``2026Q3/20260928``.

``%Y/%YQ%Q/%Y%M%D``
   Produces ``2026/2026Q3/20260928`` and is the default.

``%Y/%M/%D``
   Produces ``2026/09/28``.

Date policy
-----------

``metadata.date_priority`` lists fields in preferred order. The default order
is ``DateTimeOriginal``, ``SubSecDateTimeOriginal``, ``CreateDate``,
``MediaCreateDate``, ``TrackCreateDate``, and ``ModifyDate``. Implausible dates
before 1990 or more than one year in the future are rejected.

``timezone.default`` supplies a timezone for metadata without an embedded
offset. The date used for classification is therefore deterministic.

The optional ``date`` mapping accepts:

``process_after``
   ISO date/time below which objects are skipped.

``include_first``
   Whether the first configured day is included.

``day_starts_at``
   Number of hours subtracted before daily classification. This supports photo
   sessions that continue after midnight.

File stability and scanning
---------------------------

``stability.interval_seconds`` controls the delay between observations.
``stability.checks`` controls the required unchanged observations. Both size
and modification time must remain unchanged.

``scan.interval_seconds`` controls watch-mode polling. A one-shot command does
not sleep between scans.

Collision and duplicate policy
------------------------------

``collision.mode`` supports:

``suffix``
   Identical content is treated as an existing duplicate. Different content
   receives ``_1``, ``_2``, and so on.

``fail``
   Existing different content fails the operation.

``quarantine``
   Existing different content is routed through configured quarantine behavior.

``duplicate_detection.mode`` documents the desired duplicate strategy. The
organizer currently compares size before reading content for a collision.

Retries and quarantine
----------------------

``retry.attempts``, ``retry.initial_seconds``, and ``retry.multiplier`` define
bounded exponential backoff for I/O errors. After the final failure, the source
remains in place unless ``quarantine.path`` is configured.

Adapter configuration and secrets
---------------------------------

Adapter-specific values are keys under ``adapter``. Persistent API
configurations reject ``password``, ``access_token``, and
``secret_access_key``. Instead, store an environment variable name:

.. code-block:: yaml

   adapter:
     type: webdav
     endpoint: https://dav.example.test
     username_env: PHOTO_WEBDAV_USERNAME
     password_env: PHOTO_WEBDAV_PASSWORD

The CLI loader also accepts direct values for ephemeral YAML configuration, but
committing credentials to a repository is strongly discouraged.

Environment settings
--------------------

The Django application reads:

``DEBUG``
   Development mode; must be false in production.

``SECRET_KEY``
   Required and unique when ``DEBUG=false``.

``ALLOWED_HOSTS``, ``CORS_ALLOWED_ORIGINS``, ``CSRF_TRUSTED_ORIGINS``
   Comma-separated HTTP security settings. ``CSRF_TRUSTED_ORIGINS`` must
   include the scheme, host, and port used in the browser (for example
   ``http://127.0.0.1:8080``).

``SESSION_COOKIE_SECURE``, ``CSRF_COOKIE_SECURE``
   When ``DEBUG=false``, default to secure cookies. Set both to ``false`` only
   for local HTTP testing; use ``true`` when the site is served over HTTPS.

``DATABASE_URL``
   PostgreSQL or another URL supported by ``dj-database-url``. When absent,
   SQLite uses ``DATABASE_PATH``.

``MEDIA_ROOT``, ``LOG_DIR``
   Thumbnail/media storage and default ingestion log location.
