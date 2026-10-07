# Changelog

All notable changes to PhotoChart are documented in this file.

## [Unreleased]

### Added

- ``extract_exif(..., full=True)`` for multi-IFD EXIF extraction; ``pchart info
  --all`` / ``-a`` and machine-readable ``pchart info --json`` / ``-j``.
- ``pchart ingest --raw`` / ``-r`` (and ``IngestJob.raw_only``) to ingest only
  camera RAW extensions from ``RAW_IMAGE_EXTENSIONS``, including catalog
  pre-selection of not-yet-catalogued files.

## [v0.4.0] - 2026-10-05

### Added

- Removable-media and host-path workflows: `scripts/compose-organize.sh` (device →
  library organize), `scripts/compose-ingest.sh` (one-shot catalog ingest with
  tight read-only bind-mounts), and `scripts/compose-run.sh` (generic
  `docker compose run` wrapper with `--from-path` / `--mount` for any `pchart`
  command).
- `photochart.fs.mounts` and `photochart.ingest.runner` for path validation,
  mount-root resolution, stable device labels, and local vs one-shot Docker
  ingest dispatch (`choose_and_run_ingest`, `run_ingest_docker`).
- Optional API-driven ingest from paths outside the worker namespace:
  `IngestJob` model, Celery `run_ingest_job` task, and `POST/GET
  /api/ingest-jobs/` (operators create; authenticated users read status).
- Django settings `INGEST_DOCKER_ENABLED`, `INGEST_ALLOWED_PATH_PREFIXES`,
  `INGEST_ALWAYS_ALLOWED_PREFIXES`, `INGEST_HOST_ROOT`, `INGEST_COMPOSE_FILE`,
  and `COMPOSE_PROJECT_NAME`, documented in `.env.example` and deployment docs.
- `pchart ingest --device` for a stable `PhotoPath.device` label on bind-mounted
  external drives.
- Compose `ingest` one-shot service (`tools` profile) and example organizer
  YAML under `examples/organizer/` (including removable-inbox) for host-native
  organize.
- `get_mount_point_from_file` and `device_label_for_path` in
  `photochart.fs.device` for host mount tables and shared label logic.
- Operations, CLI, deployment, Django API, and development docs for the
  organize → ingest playbook, command matrix, and `compose.override.yaml`
  Docker-socket ingest setup.
- First-class host PostgreSQL + Docker UI topology via
  `compose.host-postgres.yaml`, documented in `docs/compose_host_postgres.rst`,
  so host `.venv` commands and Compose services share one database and media
  directory without changing the default bundled-PostgreSQL stack.
- `scripts/check-host-postgres.sh` to verify PostgreSQL is reachable from both
  the host and a Docker container.
- First-class host PostgreSQL + Docker UI topology via
  `docker/compose.host-postgres.yaml`, documented in `docs/compose_host_postgres.rst`,
  so host `.venv` commands and Compose services share one database and media
  directory without changing the default bundled-PostgreSQL stack.
- `scripts/check-host-postgres.sh` to verify PostgreSQL is reachable from both
  the host and a Docker container.
- ``pchart ingest --retry-thumbnails`` (and ``IngestJob.retry_thumbnails``) to
  backfill missing thumbnails for already-catalogued files without creating new
  ``PhotoPath`` rows. The progress bar counts only catalogued files missing
  thumbnails, not every image under the ingest path.
- ``pchart resize-thumbnails --resolution`` to bulk-resize stored catalog
  thumbnails in the media volume, with optional ``--max-size`` to skip smaller
  files (e.g. ``800K``, ``10M``, ``1G``).

### Changed

- Example organizer YAML (`organizer.example.yaml`,
  `organizer.removable-inbox.example.yaml`) moved from the repository root to
  `examples/organizer/`; README, `docs/configuration.rst`, `docs/getting_started.rst`,
  `docs/cli.rst`, and `docs/operations.rst` updated to point operators there.
- Reorganized the `photochart` package into `common/`, `fs/`, `media/`,
  `imaging/`, and `ingest/` subpackages; imports updated across backend, CLI,
  organizer, and tests (`photochart.ingest.photos`, `photochart.media.extensions`,
  `photochart.fs.protocols`, and related modules).
- CLI `pchart ingest` routes through `choose_and_run_ingest` so host-visible and
  Docker-backed external paths use the same code path as Celery ingest jobs.
- README and `docs/getting_started.rst` describe local development with
  `runserver` on port 8000, Vite on `:5173`, and `createsuperuser` before sign-in.
- Frontend API client surfaces Django `detail` messages on failed HTTP
  responses (for example invalid login credentials).
- Compose database settings are parameterized with `POSTGRES_DB`,
  `POSTGRES_USER`, `POSTGRES_PORT`, and `COMPOSE_DATABASE_HOST`, and migrations
  now wait for the configured database instead of depending directly on the
  bundled `db` service.
- Docker-backed ingest honors Docker Compose's multi-file `COMPOSE_FILE` value
  so API-triggered one-shot containers use the same Compose topology as the
  worker.
- Docker Compose files and the application `Dockerfile` live under `docker/`.
  Run Compose from the repository root with `--project-directory .` and
  `-f docker/compose.yaml` (host PostgreSQL: add `-f docker/compose.host-postgres.yaml`
  or set `COMPOSE_FILE` as documented).  Helper scripts source
  `scripts/lib/compose.sh` for the same flags.
- ``docker/compose.host-postgres.yaml`` includes the base stack via Compose
  ``include``, so host PostgreSQL can be started with a single ``-f`` file.
- Compose database settings are parameterized with `POSTGRES_DB`,
  `POSTGRES_USER`, `POSTGRES_PORT`, and `COMPOSE_DATABASE_HOST`, and migrations
  now wait for the configured database instead of depending directly on the
  bundled `db` service.
- Docker-backed ingest honors Docker Compose's multi-file `COMPOSE_FILE` value
  so API-triggered one-shot containers use the same Compose topology as the
  worker.
- Ingest thumbnails under `MEDIA_ROOT` use a two-level directory tree
  (`photographs/ab/cd/...`) instead of three (`photographs/ab/cd/ef/...`) via
  `photograph_upload_path` in `backend/photograph/models.py`; existing stored
  paths are unchanged until thumbnails are written again.
- ``pchart ingest`` progress counts only files not yet catalogued on the ingest
  device; the CLI and ingest log report how many were skipped as already
  catalogued.
- ``pchart ingest`` (normal mode) pre-filters already-catalogued files before
  the progress loop: only pending files are counted and processed. The CLI
  prints ``Skipped N already catalogued photo(s).`` when applicable; the ingest
  log records skip and pending counts. Ingest results include
  ``skipped_already_ingested``.
- Ingest scan and pre-filter performance: ``/proc/mounts`` is read once per run
  via ``load_mount_table`` / ``mount_point_for_path``; stored paths are derived
  from a cached mount table instead of per-file mount lookups; ``MEDIA_ROOT`` is
  resolved once during filesystem walks. Catalog membership checks use batched
  ``PhotoPath`` queries (chunked ``path__in``, or ``path__startswith`` when
  the ingest tree maps to a safe prefix and that is cheaper than scanning the
  full on-disk file list).
- ``pchart ingest --retry-thumbnails`` uses the same batched ``PhotoPath``
  lookup strategy when matching on-disk files to catalog rows (with
  ``select_related`` for thumbnails), instead of one database query per scanned
  file. Thumbnail retry still shares the single mount-table load and cached
  ``MEDIA_ROOT`` handling with normal ingest.

### Fixed

- Ingest thumbnail storage retries transient reads from flaky mounts (e.g. pCloud
  Drive FUSE): buffered reads with size checks, optional stability wait, and
  configurable ``INGEST_READ_RETRY_*`` settings.
- Host PostgreSQL Compose overlay bind-mounts host ``MEDIA_ROOT`` from ``.env``
  (with ``PHOTOCHART_MEDIA_PATH`` as fallback) into ``web``, worker, and gateway
  so nginx ``X-Accel-Redirect`` serves the same thumbnail tree as host
  ``pchart ingest``; troubleshooting docs cover stale binds after recreating the
  media directory (``findmnt`` ``//deleted`` → recreate media-mounted services).
- Nginx gateway forwards ``$http_host`` (including port) as ``Host`` and
  ``X-Forwarded-Host`` so API ``image_url`` values match the published gateway
  URL (for example ``http://localhost:8090/media/...``).
- Vite dev server proxies `/api` and `/media` to Django on `127.0.0.1:8000`
  so the React app at `http://localhost:5173` can authenticate without Docker
  or a manual `VITE_API_BASE_URL` (`frontend/vite.config.ts`).
- Nginx gateway re-resolves the ``web`` upstream via Docker DNS so API and
  health checks do not return 502 after the ``web`` container is recreated.
- Compose defaults ``ALLOWED_HOSTS`` to include ``web`` for internal proxy
  requests.


## [v0.3.2] - 2026-10-04

### Fixed

- Gateway Nginx `root` for the built frontend so `/` serves the SPA instead of
  looping on `try_files` and returning 500.
- Docker Compose login over HTTP when `DEBUG=false`: configurable
  `SESSION_COOKIE_SECURE` and `CSRF_COOKIE_SECURE`, default trusted CSRF
  origins from `PHOTOCHART_PORT`, and documentation for production HTTPS.

## [v0.3.1] - 2026-09-30

### Added

- Central `photochart.media_extensions` module listing raster, RAW, HEIC/HEIF,
  and video extensions, with shared organizer defaults.
- `RawPyBackend` for all registered RAW extensions (replacing NEF-only
  processing), using embedded previews or full RAW conversion via rawpy.

### Changed

- Media file extensions are normalized to lowercase with a leading dot in
  organizer configuration, discovery, YAML loading, and related checks; matching
  is case-insensitive everywhere extensions are compared.
- Metadata date correction accepts the same image extension set as ingestion.
- Organizer and Django default `media_extensions` now include common RAW formats
  in addition to prior raster and video types.

## [v0.3.0] - 2026-09-30

### Added

- Verified copy-before-delete transfers, explicit quarantine failures, and
  transient/permanent retry classification across organizer adapters.
- Complete persisted organizer configuration, honest single-worker semantics,
  discover-only scanning, and operation object identifiers.
- Same-origin session authentication, CSRF protection, operator permissions,
  and authenticated media delivery.
- Durable Celery jobs with PostgreSQL leases, cancellation, heartbeats, stale
  recovery, failed-object retry, filtering, and bounded API payloads.
- Worker-backed planned actions and duplicate scans with idempotency, state,
  provenance, and persistent audit records.
- Docker Compose production stack with PostgreSQL, Redis, Gunicorn, Celery,
  Nginx, secure proxy settings, structured logs, metrics, and alert rules.
- Automated CI, provider acceptance contracts, backup/restore tooling, package
  builds, and release validation.

### Fixed

- Dynamic version, automatic detection of software version based on tag.

## [v0.2.0] - 2026-09-29

### Added

- Python package, project metadata, dynamic versioning, pre-commit checks, and
  Django application foundation.
- Photograph catalog with checksums, EXIF capture time, camera model, error
  state, thumbnails, albums, and multiple paths per photograph.
- Portable filesystem cataloging with device detection, mount-relative paths,
  filenames, sizes, timestamps, and checksum-based media sharding.
- Recursive ingestion with per-file transactions, progress reporting,
  configurable checksums, image storage and resizing, generated-media
  protection, logging, and reconciliation tooling.
- JPEG, PNG, TIFF, NEF, and RAW metadata inspection and conversion, including
  embedded preview extraction and reusable resolution presets.
- `pchart` CLI for ingestion, metadata inspection, conversion, organization,
  duplicate reporting, missing-copy analysis, and capture-date correction.
- Unified Photo Organizer with storage-independent domain models, adapter
  capabilities, YAML configuration, media filtering, stability checks,
  retries, quarantine, dry-run, one-shot, scan, and watch modes.
- Configurable classification patterns using `%Y`, `%M`, `%D`, `%Q`, and `%%`,
  with protection against absolute paths and directory traversal.
- Capture-date selection with configurable metadata priority, plausibility
  checks, timezone handling, ExifTool support, Pillow/RAW fallback, filesystem
  fallback, and date provenance.
- Safe copy and move workflows with disk-space checks, temporary files,
  integrity verification, content-aware collision handling, duplicate
  recognition, and incrementing filename suffixes.
- Duplicate grouping with SHA-256 comparison, reclaimable-space summaries, and
  dry-run-first metadata correction with backup and post-write verification.
- Storage adapters for local filesystems, NAS/SMB/NFS mounts, pCloud Drive,
  pCloud API, WebDAV, Nextcloud, SFTP, AWS S3, and S3-compatible services.
- Provider safeguards including pCloud Drive mount confinement,
  environment-based credentials, SFTP host-key verification, WebDAV
  server-side operations, and verified S3 copy-before-delete moves.
- Django REST API for photographs, paths, checksums, directories, locations,
  albums, planned actions, organizer configurations, jobs, operations,
  duplicate groups, and readiness checks.
- Persistent organizer jobs and per-object audit records, retry endpoints,
  local catalog synchronization, Django admin integration, and database
  migrations.
- React and TypeScript interface for date-based photo browsing, device and path
  navigation, thumbnails, metadata, selection controls, albums, planned
  actions, and organizer job management.
- Environment-driven SQLite and PostgreSQL support, configurable
  host/CORS/CSRF/cookie security, optional dependency groups, and example
  environment and organizer configurations.
- Automated tests covering CLI isolation, file protocols, path patterns,
  metadata resolution, local organization, collisions, reports, pCloud Drive,
  remote adapter construction, verified S3 moves, Django models, serializers,
  and health checks.
- Comprehensive Sphinx manual for installation, architecture, configuration,
  CLI usage, adapters, operations, recovery, REST integration, deployment,
  security, development, and Python APIs.
- Makefile targets for strict HTML documentation, LaTeX source and PDF builds,
  link checking, help, and cleanup.
