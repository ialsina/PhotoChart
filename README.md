# PhotoChart and Unified Photo Organizer

PhotoChart catalogs, browses, deduplicates, and organizes photo and video
collections. The organizer core is independent of Django and storage providers;
the Django API and React UI add configuration, execution, and audit history.

## Documentation

The comprehensive Sphinx manual lives in `docs/`:

```bash
pip install -e ".[docs]"
make html
make pdf-latex
```

HTML is written to `docs/_build/html`; the PDF is written to
`docs/_build/latex/PhotoChart.pdf`.

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[nef,remote,s3,dev]"
cp .env.example .env
python backend/manage.py migrate
```

Install ExifTool through the operating system for complete image, RAW, and video
capture-date support. Pillow metadata and filesystem modification time are used
as fallbacks.

## Organize local media

Copy `examples/organizer/organizer.example.yaml` to `organizer.yaml`, adjust
the paths, and preview:

```bash
pchart organize once organizer.yaml --dry-run
```

Run once or continuously:

```bash
pchart organize once organizer.yaml
pchart organize watch organizer.yaml
```

The default classification pattern is `%Y/%YQ%Q/%Y%M%D`, producing
`2026/2026Q3/20260928`. `%YQ%Q/%Y%M%D` produces
`2026Q3/20260928`. Supported tokens are:

- `%Y`: four-digit year
- `%M`: two-digit month
- `%D`: two-digit day
- `%Q`: quarter number
- `%%`: literal percent

This is an organizer-specific pattern language; `%M` intentionally means month,
not the `strftime` minute token.

## Safety behavior

- Files must have unchanged size and modification time across configured checks.
- Embedded capture dates are preferred and their source is recorded.
- Existing identical content is treated as a duplicate.
- Different content receives a numeric suffix by default.
- Copy mode verifies source and destination content.
- Object-storage moves copy, verify, and only then delete the source.
- Failed files remain at the source or move to configured quarantine.
- `--dry-run` never mutates storage.

## Storage adapters

Supported adapter types are `local`, `pcloud_drive`, `pcloud_api`, `webdav`,
`nextcloud`, `sftp`, and `s3`. NAS, SMB, and NFS mounts use `local`.

Provider options belong under `adapter`. Store only environment-variable names
in persistent Django configurations:

```yaml
adapter:
  type: pcloud_api
  endpoint: https://api.pcloud.com
  access_token_env: PCLOUD_ACCESS_TOKEN
```

WebDAV and Nextcloud use `username_env` and `password_env`; SFTP additionally
supports `key_filename` and `known_hosts`; S3 uses the standard AWS credential
chain or `access_key_id_env` and `secret_access_key_env`.

## Reports and metadata correction

```bash
pchart duplicates /data/Photos
pchart duplicates /card --missing-against /data/Photos
pchart metadata-date photo.jpg 2026-09-28T14:23:18
pchart metadata-date photo.jpg 2026-09-28T14:23:18 --apply
```

Metadata correction is a dry-run by default and retains ExifTool backups unless
`--no-backup` is explicitly supplied.

## Web application

```bash
python backend/manage.py migrate
python backend/manage.py createsuperuser
python backend/manage.py runserver
npm --prefix frontend run dev
```

Open `http://localhost:5173` (Vite proxies `/api` to Django on port 8000).

Organizer configurations, dry-run execution, jobs, and operation history are
available through `/api/organizer-*` and the Organizer frontend tab. Readiness
is exposed at `/api/organizer-health/`.

For production, set `DEBUG=false`, a unique `SECRET_KEY`, `ALLOWED_HOSTS`,
trusted origins, and either `DATABASE_URL` for PostgreSQL or `DATABASE_PATH` for
SQLite. Run the organizer under a single-worker systemd service or timer first;
increase concurrency only after provider acceptance tests.

Docker Compose supports two PostgreSQL topologies:

- Default `docker/compose.yaml`: bundled PostgreSQL in the `db` service and Docker
  volume.
- Host PostgreSQL with Docker UI: use
  `COMPOSE_FILE=docker/compose.yaml:docker/compose.host-postgres.yaml` (with
  `docker compose --project-directory .`) so host `.venv`
  commands and Compose services share the same host database and media path.
  See `docs/compose_host_postgres.rst`.

## Migration from PhotoClassify

PhotoClassify's copy/classification, collision suffixing, duplicate/missing-copy
reports, incremental date policies, and metadata correction are implemented
here. Run reports and dry-run classification against the old source and
destination before enabling move mode. The experimental PhotoClassify catalog
and duplicate relationship schemas are replaced by PhotoChart organizer jobs,
operations, and duplicate groups.

## Verification

```bash
python -m pytest tests --no-cov
python backend/manage.py test organizer
python backend/manage.py check --deploy
npm --prefix frontend run build
```
