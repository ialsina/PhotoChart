#!/usr/bin/env bash
set -euo pipefail

SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=scripts/lib/compose.sh
source "${SCRIPTS_DIR}/lib/compose.sh"
photochart_compose_init

if [[ ${1:-} != "--confirm" || -z ${2:-} ]]; then
  echo "Usage: $0 --confirm BACKUP_DIRECTORY" >&2
  exit 2
fi

backup=$2
(
  cd "$backup"
  sha256sum --check SHA256SUMS
)

docker compose "${PHOTOCHART_COMPOSE_ARGS[@]}" stop gateway web worker beat
docker compose "${PHOTOCHART_COMPOSE_ARGS[@]}" exec -T db \
  pg_restore --username photochart --dbname photochart \
  --clean --if-exists --no-owner \
  < "$backup/database.dump"
docker compose "${PHOTOCHART_COMPOSE_ARGS[@]}" run --rm --no-deps --user root init-volumes \
  sh -c 'find /app/backend/media -mindepth 1 -delete; tar -C /app/backend/media -xzf -' \
  < "$backup/media.tar.gz"
docker compose "${PHOTOCHART_COMPOSE_ARGS[@]}" run --rm migrate
docker compose "${PHOTOCHART_COMPOSE_ARGS[@]}" up -d web worker beat gateway

echo "Restore complete. Verify /readyz and perform a catalog reconciliation."
