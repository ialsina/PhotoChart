# Changelog

All notable changes to PhotoChart are documented in this file.

## [Unreleased]

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
