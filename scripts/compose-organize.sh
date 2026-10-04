#!/usr/bin/env bash
# scripts/compose-organize.sh
#
# Copy/move photos from a removable inbox (USB drive, SD card, host directory)
# into the shared library and then remind you to run the ingest step.
#
# This is a thin wrapper around compose-run.sh for the most common "device →
# library" workflow.  It generates a minimal organizer YAML on the fly, then
# passes it into a one-shot container.
#
# Usage:
#   ./scripts/compose-organize.sh SOURCE_DIR [OPTIONS]
#
# Options:
#   --dry-run          Preview actions without moving or copying files.
#   --copy             Copy files (keep source intact). Default.
#   --move             Move files (removes source after verified copy).
#   --pattern PATTERN  Override destination pattern
#                      (default: %Y/%YQ%Q/%Y%M%D).
#   --dest PATH        Container-side destination path
#                      (default: /photos/Photos or $PHOTO_DEST_PATH).
#   --quarantine PATH  Container-side quarantine path
#                      (default: /photos/OrganizerQuarantine or $PHOTO_QUARANTINE_PATH).
#   -h, --help         Show this help.
#
# Environment variables (with defaults):
#   PHOTO_DEST_PATH        Destination inside the container [/photos/Photos]
#   PHOTO_QUARANTINE_PATH  Quarantine path inside the container
#                          [/photos/OrganizerQuarantine]
#
# Examples:
#   # Preview what would be copied from a Canon card:
#   ./scripts/compose-organize.sh /run/media/$USER/EOS_DIGITAL/DCIM --dry-run
#
#   # Copy and then ingest:
#   ./scripts/compose-organize.sh /run/media/$USER/EOS_DIGITAL/DCIM --copy
#   ./scripts/compose-ingest.sh /photos/Photos
#
#   # Move (use with caution – removes source files after verified copy):
#   ./scripts/compose-organize.sh /mnt/inbox --move
#
# After organize completes, run:
#   ./scripts/compose-ingest.sh /photos/Photos
# to catalog the newly imported files.
#
set -euo pipefail

SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=scripts/lib/mounts.sh
source "${SCRIPTS_DIR}/lib/mounts.sh"

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
PHOTO_DEST_PATH="${PHOTO_DEST_PATH:-/photos/Photos}"
PHOTO_QUARANTINE_PATH="${PHOTO_QUARANTINE_PATH:-/photos/OrganizerQuarantine}"
DEFAULT_PATTERN="%Y/%YQ%Q/%Y%M%D"

# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------
usage() {
  cat <<'EOF'
Usage: ./scripts/compose-organize.sh SOURCE_DIR [OPTIONS]

Copy/move photos from SOURCE_DIR into the shared library.

Options:
  --dry-run            Preview actions without moving or copying files.
  --copy               Copy files (keep source intact). Default.
  --move               Move files (removes source after verified copy).
  --pattern PATTERN    Override destination naming pattern
                       (default: %Y/%YQ%Q/%Y%M%D).
  --dest PATH          Override container destination path
                       (default: /photos/Photos).
  --quarantine PATH    Override container quarantine path
                       (default: /photos/OrganizerQuarantine).
  -h, --help           Show this help.

After organize completes, run:
  ./scripts/compose-ingest.sh /photos/Photos

EOF
  exit 0
}

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
if [[ $# -lt 1 || "$1" == "-h" || "$1" == "--help" ]]; then
  usage
fi

SOURCE_DIR="$1"
shift

MODE="copy"
DRY_RUN=""
PATTERN="$DEFAULT_PATTERN"
DEST_PATH="$PHOTO_DEST_PATH"
QUARANTINE_PATH="$PHOTO_QUARANTINE_PATH"
EXTRA_PCHART_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN="--dry-run"
      shift
      ;;
    --copy)
      MODE="copy"
      shift
      ;;
    --move)
      MODE="move"
      shift
      ;;
    --pattern)
      [[ $# -lt 2 ]] && { echo "ERROR: --pattern requires an argument." >&2; exit 1; }
      PATTERN="$2"
      shift 2
      ;;
    --dest)
      [[ $# -lt 2 ]] && { echo "ERROR: --dest requires an argument." >&2; exit 1; }
      DEST_PATH="$2"
      shift 2
      ;;
    --quarantine)
      [[ $# -lt 2 ]] && { echo "ERROR: --quarantine requires an argument." >&2; exit 1; }
      QUARANTINE_PATH="$2"
      shift 2
      ;;
    -h|--help)
      usage
      ;;
    *)
      echo "ERROR: Unknown option: $1" >&2
      echo "Run with --help for usage." >&2
      exit 1
      ;;
  esac
done

# ---------------------------------------------------------------------------
# Validate source path
# ---------------------------------------------------------------------------
ABS_SOURCE="$(pchart_validate_host_path "$SOURCE_DIR")"
MOUNT_ROOT="$(pchart_resolve_mount_root "$ABS_SOURCE")"

# Warn if source is not readable
if [[ -e "$ABS_SOURCE" && ! -r "$ABS_SOURCE" ]]; then
  echo "WARNING: $ABS_SOURCE is not readable by the current user." >&2
  echo "         The container (uid 10001) may fail to read it." >&2
fi

# For --move, the source mount needs :rw so the container can delete source files.
if [[ "$MODE" == "move" ]]; then
  MOUNT_MODE="rw"
  echo "WARNING: --move will DELETE source files from $ABS_SOURCE after copy." >&2
  echo "         Ensure you have a backup before proceeding." >&2
  echo ""
else
  MOUNT_MODE="ro"
fi

# ---------------------------------------------------------------------------
# Generate a temporary organizer YAML in /tmp
# ---------------------------------------------------------------------------
TMP_YAML="$(mktemp /tmp/pchart-organize-XXXXXX.yaml)"
trap 'rm -f "$TMP_YAML"' EXIT

cat > "$TMP_YAML" <<YAML
# Auto-generated by scripts/compose-organize.sh
# Source:      $ABS_SOURCE
# Destination: $DEST_PATH
# Mode:        $MODE
adapter:
  type: local

source:
  path: "$ABS_SOURCE"

destination:
  path: "$DEST_PATH"
  pattern: "$PATTERN"

quarantine:
  path: "$QUARANTINE_PATH"

mode: $MODE
workers: 1

scan:
  interval_seconds: 60

stability:
  interval_seconds: 30
  checks: 2

metadata:
  date_priority:
    - DateTimeOriginal
    - SubSecDateTimeOriginal
    - CreateDate
    - MediaCreateDate
    - TrackCreateDate
    - ModifyDate

collision:
  mode: suffix

duplicate_detection:
  mode: size_then_hash

retry:
  attempts: 4
  initial_seconds: 5
  multiplier: 3
YAML

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo "Source         : $ABS_SOURCE"
echo "Mount root     : $MOUNT_ROOT (bind-mounted :${MOUNT_MODE})"
echo "Destination    : $DEST_PATH"
echo "Quarantine     : $QUARANTINE_PATH"
echo "Mode           : $MODE"
echo "Pattern        : $PATTERN"
[[ -n "$DRY_RUN" ]] && echo "Action         : DRY RUN (no files will be moved/copied)"
echo ""

# ---------------------------------------------------------------------------
# Mount the generated YAML into the container at a fixed path
# ---------------------------------------------------------------------------
CONTAINER_YAML="/tmp/pchart-organize.yaml"

# Build bind flags:
#   - source mount root (ro or rw depending on mode)
#   - YAML file (ro)
BIND_FLAGS=(
  "-v" "${MOUNT_ROOT}:${MOUNT_ROOT}:${MOUNT_MODE}"
  "-v" "${TMP_YAML}:${CONTAINER_YAML}:ro"
)

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
docker compose run --rm --no-deps \
  "${BIND_FLAGS[@]}" \
  web \
  pchart organize once "$CONTAINER_YAML" \
  ${DRY_RUN:+--dry-run} \
  "${EXTRA_PCHART_ARGS[@]+"${EXTRA_PCHART_ARGS[@]}"}"

echo ""
echo "────────────────────────────────────────────────────────────"
if [[ -n "$DRY_RUN" ]]; then
  echo "Dry run complete.  Re-run without --dry-run to apply changes."
  echo "Then catalog the library with:"
else
  echo "Organize complete.  Catalog the library with:"
fi
echo "  ./scripts/compose-ingest.sh $DEST_PATH"
echo "────────────────────────────────────────────────────────────"
