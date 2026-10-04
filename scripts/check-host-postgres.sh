#!/usr/bin/env bash
# Verify the host PostgreSQL topology from both the host and a container.

set -euo pipefail

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "DATABASE_URL must point at the host PostgreSQL database." >&2
  exit 2
fi

if ! command -v psql >/dev/null 2>&1; then
  echo "psql is required on the host." >&2
  exit 2
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required for the container connectivity check." >&2
  exit 2
fi

container_url="$(
  python - <<'PY'
import os
from urllib.parse import urlsplit, urlunsplit

url = os.environ["DATABASE_URL"]
parts = urlsplit(url)
if not parts.hostname:
    raise SystemExit("DATABASE_URL must include a hostname")

if "@" in parts.netloc:
    auth, _host = parts.netloc.rsplit("@", 1)
    auth = f"{auth}@"
else:
    auth = ""

port = f":{parts.port}" if parts.port else ""
netloc = f"{auth}host.docker.internal{port}"
print(urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment)))
PY
)"

echo "Checking host PostgreSQL connection..."
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -c "select 1 as host_ok;"

echo "Checking container-to-host PostgreSQL connection..."
docker run --rm --add-host=host.docker.internal:host-gateway postgres:16-alpine \
  psql "$container_url" -v ON_ERROR_STOP=1 -c "select 1 as container_ok;"

echo "Host PostgreSQL is reachable from both host and Docker."
