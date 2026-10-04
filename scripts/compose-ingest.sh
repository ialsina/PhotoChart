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
       docker compose run --rm --no-deps \\
         -v <mount_root>:<mount_root>:ro \\
         web pchart ingest <PATH> --device "<label>" [options]

Options forwarded to pchart ingest:
  --no-checksum       Skip checksum calculation
  --no-recursive      Do not recurse into subdirectories
  --no-store-images   Do not copy thumbnails into the media volume
  --resolution <R>    Resize thumbnails (e.g. 1920x1080, high, medium)
  --log <PATH>        Log file or directory for detailed error output

EOF
  exit 0
fi

INGEST_PATH="$1"
shift  # remaining args are forwarded to pchart ingest

# ---------------------------------------------------------------------------
# Resolve absolute path
# ---------------------------------------------------------------------------
ABS_PATH="$(realpath -m -- "$INGEST_PATH")"

# Reject dangerous roots
for DANGEROUS in /proc /sys /dev /run/docker.sock /var/run/docker.sock; do
  if [[ "$ABS_PATH" == "$DANGEROUS" || "$ABS_PATH" == "$DANGEROUS/"* ]]; then
    echo "ERROR: Refusing to ingest from restricted system path: $ABS_PATH" >&2
    exit 1
  fi
done
if [[ "$ABS_PATH" == "/" ]]; then
  echo "ERROR: Refusing to ingest from the filesystem root '/'." >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Resolve mount root via findmnt
# ---------------------------------------------------------------------------
MOUNT_ROOT=""
if command -v findmnt &>/dev/null; then
  MOUNT_ROOT="$(findmnt -T "$ABS_PATH" --output TARGET --noheadings --raw 2>/dev/null || true)"
  # Reject root filesystem – use the path's own directory in that case
  if [[ "$MOUNT_ROOT" == "/" ]]; then
    MOUNT_ROOT=""
  fi
fi

if [[ -z "$MOUNT_ROOT" ]]; then
  # Fall back to the path itself (or its parent if it's a file)
  if [[ -f "$ABS_PATH" ]]; then
    MOUNT_ROOT="$(dirname "$ABS_PATH")"
  else
    MOUNT_ROOT="$ABS_PATH"
  fi
fi

# ---------------------------------------------------------------------------
# Build device label
# ---------------------------------------------------------------------------
DEVICE_LABEL=""
if command -v findmnt &>/dev/null; then
  FINDMNT_OUT="$(findmnt -T "$ABS_PATH" --output LABEL,TARGET --noheadings --raw 2>/dev/null || true)"
  if [[ -n "$FINDMNT_OUT" ]]; then
    LABEL_PART="$(echo "$FINDMNT_OUT" | awk '{print $1}')"
    TARGET_PART="$(echo "$FINDMNT_OUT" | awk '{print $2}')"
    if [[ -n "$LABEL_PART" && "$LABEL_PART" != "-" ]]; then
      DEVICE_LABEL="${LABEL_PART} (${TARGET_PART})"
    elif [[ -n "$TARGET_PART" && "$TARGET_PART" != "/" ]]; then
      DEVICE_LABEL="$TARGET_PART"
    fi
  fi
fi

if [[ -z "$DEVICE_LABEL" ]]; then
  # Use the mount root name as a minimal label
  DEVICE_LABEL="$(basename "$MOUNT_ROOT")"
fi

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
exec docker compose run --rm --no-deps \
  -v "${MOUNT_ROOT}:${MOUNT_ROOT}:ro" \
  web \
  pchart ingest "$ABS_PATH" --device "$DEVICE_LABEL" "$@"
