#!/usr/bin/env bash
set -euo pipefail

if [[ ${1:-} != "--confirm" || -z ${2:-} ]]; then
  echo "Usage: $0 --confirm BACKUP_DIRECTORY" >&2
  exit 2
fi

backup=$2
(
  cd "$backup"
  sha256sum --check SHA256SUMS
)

docker compose stop gateway web worker beat
docker compose exec -T db \
  pg_restore --username photochart --dbname photochart \
  --clean --if-exists --no-owner \
  < "$backup/database.dump"
docker compose run --rm --no-deps --user root init-volumes \
  sh -c 'find /app/backend/media -mindepth 1 -delete; tar -C /app/backend/media -xzf -' \
  < "$backup/media.tar.gz"
docker compose run --rm migrate
docker compose up -d web worker beat gateway

echo "Restore complete. Verify /readyz and perform a catalog reconciliation."
