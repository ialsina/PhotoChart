#!/usr/bin/env bash
set -euo pipefail

umask 077
destination=${1:-backups/$(date -u +%Y%m%dT%H%M%SZ)}
mkdir -p "$destination"

docker compose exec -T db \
  pg_dump --username photochart --format=custom photochart \
  > "$destination/database.dump"
docker compose run --rm --no-deps --user root init-volumes \
  tar -C /app/backend/media -czf - . \
  > "$destination/media.tar.gz"

cp compose.yaml "$destination/compose.yaml"
cp .env "$destination/environment.env"
sha256sum \
  "$destination/database.dump" \
  "$destination/media.tar.gz" \
  "$destination/compose.yaml" \
  "$destination/environment.env" \
  > "$destination/SHA256SUMS"

echo "Backup written to $destination"
