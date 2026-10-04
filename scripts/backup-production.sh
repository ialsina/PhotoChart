#!/usr/bin/env bash
set -euo pipefail

SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=scripts/lib/compose.sh
source "${SCRIPTS_DIR}/lib/compose.sh"
photochart_compose_init

umask 077
destination=${1:-backups/$(date -u +%Y%m%dT%H%M%SZ)}
mkdir -p "$destination"

docker compose "${PHOTOCHART_COMPOSE_ARGS[@]}" exec -T db \
  pg_dump --username photochart --format=custom photochart \
  > "$destination/database.dump"
docker compose "${PHOTOCHART_COMPOSE_ARGS[@]}" run --rm --no-deps --user root init-volumes \
  tar -C /app/backend/media -czf - . \
  > "$destination/media.tar.gz"

cp docker/compose.yaml "$destination/compose.yaml"
cp .env "$destination/environment.env"
sha256sum \
  "$destination/database.dump" \
  "$destination/media.tar.gz" \
  "$destination/compose.yaml" \
  "$destination/environment.env" \
  > "$destination/SHA256SUMS"

echo "Backup written to $destination"
