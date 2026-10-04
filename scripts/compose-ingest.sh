#!/usr/bin/env bash
# scripts/compose-ingest.sh
#
# Ingest photos from a host path (USB drive, SD card, or any directory not
# permanently bind-mounted into the Docker Compose stack) by launching a
# one-shot container that mounts only the device's root read-only.
#
# Usage:
#   ./scripts/compose-ingest.sh <PATH> [pchart-ingest-options...]
#
# Examples:
#   ./scripts/compose-ingest.sh /mnt/camera/DCIM
#   ./scripts/compose-ingest.sh /media/$USER/EOS_DIGITAL/DCIM --no-store-images
#   ./scripts/compose-ingest.sh /run/media/$USER/SD_CARD --no-checksum
#
# Requirements:
#   - Docker Compose stack must be running (docker compose up -d).
#   - findmnt (part of util-linux, standard on Linux).
#   - The host user must be able to read the target path.
#
# Security:
#   - Only the device's mount root is bind-mounted (read-only).
#   - The container runs as uid 10001 (photochart); paths must be world- or
#     group-readable for this uid to access them.
#   - The root filesystem ("/") is never mounted.
#
set -euo pipefail

SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=scripts/lib/mounts.sh
source "${SCRIPTS_DIR}/lib/mounts.sh"
# shellcheck source=scripts/lib/compose.sh
source "${SCRIPTS_DIR}/lib/compose.sh"
photochart_compose_init

# ---------------------------------------------------------------------------
# Arguments
# ---------------------------------------------------------------------------
if [[ $# -lt 1 || "$1" == "-h" || "$1" == "--help" ]]; then
  cat <<'EOF'
Usage: ./scripts/compose-ingest.sh <PATH> [pchart ingest options]

Ingest photos from a host path that is not permanently mounted in the
Docker Compose stack.  The script:

  1. Resolves the absolute path.
  2. Uses findmnt to find the filesystem mount root (so the bind-mount is
     as tight as possible while still giving the container a valid
     /proc/mounts entry for device detection).
  3. Builds a stable device label (e.g. "MyDisk (/mnt/camera)").
  4. Launches a one-shot container:
       docker compose run --rm --no-deps \
         -v <mount_root>:<mount_root>:ro \
         web pchart ingest <PATH> --device "<label>" [options]

Options forwarded to pchart ingest:
  --no-checksum       Skip checksum calculation
  --no-recursive      Do not recurse into subdirectories
  --no-store-images   Do not copy thumbnails into the media volume
  --resolution <R>    Resize thumbnails (e.g. 1920x1080, high, medium)
  --log <PATH>        Log file or directory for detailed error output
  --retry-thumbnails  Retry thumbnails for already-catalogued files only

EOF
  exit 0
fi

INGEST_PATH="$1"
shift  # remaining args are forwarded to pchart ingest

# ---------------------------------------------------------------------------
# Validate and resolve absolute path
# ---------------------------------------------------------------------------
ABS_PATH="$(pchart_validate_host_path "$INGEST_PATH")"

# ---------------------------------------------------------------------------
# Resolve mount root and device label (via lib/mounts.sh helpers)
# ---------------------------------------------------------------------------
MOUNT_ROOT="$(pchart_resolve_mount_root "$ABS_PATH")"
DEVICE_LABEL="$(pchart_build_device_label "$ABS_PATH")"

# ---------------------------------------------------------------------------
# Accessibility check
# ---------------------------------------------------------------------------
# The container runs as uid 10001 (photochart).  Check whether the path is
# world-readable; warn but don't abort (the user might have set up ACLs).
if [[ -e "$ABS_PATH" ]]; then
  if [[ ! -r "$ABS_PATH" ]]; then
    echo "WARNING: $ABS_PATH is not readable by the current user." >&2
    echo "         The container (uid 10001) may fail to read it." >&2
    echo "         Consider: chmod o+r \"$ABS_PATH\" or adjust ACLs." >&2
  fi
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo "Ingesting from : $ABS_PATH"
echo "Mount root     : $MOUNT_ROOT (bind-mounted read-only)"
echo "Device label   : $DEVICE_LABEL"
echo ""

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
exec docker compose "${PHOTOCHART_COMPOSE_ARGS[@]}" run --rm --no-deps \
  -v "${MOUNT_ROOT}:${MOUNT_ROOT}:ro" \
  web \
  pchart ingest "$ABS_PATH" --device "$DEVICE_LABEL" "$@"
