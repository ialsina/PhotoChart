#!/usr/bin/env bash
# scripts/compose-run.sh
#
# Generic one-shot container runner for any `pchart` command that needs
# extra bind-mounts for host or removable-media paths.
#
# Usage:
#   ./scripts/compose-run.sh [OPTIONS] SERVICE COMMAND [ARGS...]
#
# Options (must appear before SERVICE):
#   --from-path PATH   Auto-detect mount root for PATH and bind it :ro.
#                      Repeatable.  Library paths (/photos/...) are skipped.
#   --mount SRC[:DST[:MODE]]
#                      Explicit bind: host SRC → container DST (default DST=SRC)
#                      with MODE ro|rw (default ro).  Repeatable.
#   --rw               Apply :rw to the next --from-path or bare --mount.
#   -h, --help         Show this help.
#
# Behaviour:
#   - Runs: docker compose run --rm --no-deps [binds] SERVICE COMMAND [ARGS]
#   - Library paths already on /photos need no extra bind.
#   - Paths on removable media use the device's mount root as the bind source
#     so /proc/mounts inside the container is consistent.
#
# Examples:
#   # Duplicate check: source on USB card, reference library inside Compose
#   ./scripts/compose-run.sh \
#     --from-path /run/media/$USER/EOS_DIGITAL/DCIM \
#     web pchart duplicates /run/media/$USER/EOS_DIGITAL/DCIM \
#     --missing-against /photos/Photos
#
#   # Apply EXIF date to a file on a mounted SD card (write needed):
#   ./scripts/compose-run.sh \
#     --mount /run/media/$USER/SD_CARD::/rw \
#     web pchart metadata-date /run/media/$USER/SD_CARD/IMG.JPG \
#     "2026-01-01T12:00:00" --apply
#
#   # Info/convert: read-only access to any host path:
#   ./scripts/compose-run.sh \
#     --from-path /mnt/archive \
#     web pchart info /mnt/archive/old/IMG_1234.NEF
#
set -euo pipefail

SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=scripts/lib/mounts.sh
source "${SCRIPTS_DIR}/lib/mounts.sh"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
# Prefixes that are already mounted inside the container via Compose volumes.
# Paths under these prefixes do not need an extra bind-mount.
LIBRARY_PREFIXES=("/photos")

# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------
usage() {
  cat <<'EOF'
Usage: ./scripts/compose-run.sh [OPTIONS] SERVICE COMMAND [ARGS...]

Launch a one-shot `docker compose run --rm --no-deps` container with extra
bind-mounts for host or removable-media paths.

Options (before SERVICE):
  --from-path PATH      Auto-resolve mount root for PATH and bind it :ro.
                        Repeatable.  Paths inside /photos are skipped.
  --mount SRC[:DST[:MODE]]
                        Explicit bind.  DST defaults to SRC.  MODE defaults to ro.
                        Repeatable.
  -h, --help            Show this help.

Examples:
  # Duplicate check against USB card:
  ./scripts/compose-run.sh \
    --from-path /run/media/$USER/EOS_DIGITAL/DCIM \
    web pchart duplicates /run/media/$USER/EOS_DIGITAL/DCIM \
    --missing-against /photos/Photos

  # Metadata date correction on removable card (write access required):
  ./scripts/compose-run.sh \
    --mount /run/media/$USER/SD_CARD:/run/media/$USER/SD_CARD:rw \
    web pchart metadata-date /run/media/$USER/SD_CARD/IMG.JPG \
    "2026-01-01T12:00:00" --apply

  # Convert a RAW on an archive mount (read-only):
  ./scripts/compose-run.sh \
    --from-path /mnt/archive \
    web pchart convert /mnt/archive/IMG_1234.NEF --format JPEG

EOF
  exit 0
}

# ---------------------------------------------------------------------------
# Parse options
# ---------------------------------------------------------------------------
declare -a EXTRA_BINDS=()

is_library_path() {
  local resolved
  resolved="$(realpath -m -- "$1" 2>/dev/null)" || resolved="$1"
  local pfx
  for pfx in "${LIBRARY_PREFIXES[@]}"; do
    pfx="${pfx%/}"
    if [[ "$resolved" == "$pfx" || "$resolved" == "$pfx/"* ]]; then
      return 0
    fi
  done
  return 1
}

add_from_path() {
  local path="$1"
  local mode="${2:-ro}"

  # Validate
  local abs_path
  abs_path="$(pchart_validate_host_path "$path")"

  # Skip library paths – already mounted via Compose volumes
  if is_library_path "$abs_path"; then
    return 0
  fi

  local root
  root="$(pchart_resolve_mount_root "$abs_path")"
  EXTRA_BINDS+=("-v" "${root}:${root}:${mode}")
}

add_mount() {
  # Spec: SRC[:DST[:MODE]] or SRC[:DST:rw] etc.
  local spec="$1"
  local src dst mode

  # Split on ':' – we allow up to 3 parts
  IFS=':' read -r src dst mode <<< "${spec}:::"
  src="${src:-}"
  dst="${dst:-$src}"
  mode="${mode:-ro}"

  if [[ -z "$src" ]]; then
    echo "ERROR: --mount requires a non-empty SRC." >&2
    exit 1
  fi
  if [[ "$mode" != "ro" && "$mode" != "rw" ]]; then
    # dst might contain the mode if only two parts were given
    if [[ "$dst" == "ro" || "$dst" == "rw" ]]; then
      mode="$dst"
      dst="$src"
    else
      mode="ro"
    fi
  fi

  dst="${dst:-$src}"
  EXTRA_BINDS+=("-v" "${src}:${dst}:${mode}")
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      ;;
    --from-path)
      [[ $# -lt 2 ]] && { echo "ERROR: --from-path requires a PATH argument." >&2; exit 1; }
      add_from_path "$2" "ro"
      shift 2
      ;;
    --mount)
      [[ $# -lt 2 ]] && { echo "ERROR: --mount requires a SPEC argument." >&2; exit 1; }
      add_mount "$2"
      shift 2
      ;;
    --)
      shift
      break
      ;;
    -*)
      echo "ERROR: Unknown option: $1" >&2
      echo "Run with --help for usage." >&2
      exit 1
      ;;
    *)
      # First non-option arg is the SERVICE
      break
      ;;
  esac
done

if [[ $# -lt 2 ]]; then
  echo "ERROR: SERVICE and COMMAND are required." >&2
  echo "Run with --help for usage." >&2
  exit 1
fi

SERVICE="$1"
shift

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
exec docker compose run --rm --no-deps \
  "${EXTRA_BINDS[@]}" \
  "$SERVICE" \
  "$@"
