#!/usr/bin/env bash
set -euo pipefail

REMOTE="${RCLONE_REMOTE:-gdrive}"
DRIVE_BASE="${PROPERTYIQ_GDRIVE_PATH:-propertyiq_getdata/data}"
LOCAL_DATA_DIR="${PROPERTYIQ_LOCAL_DATA_DIR:-data}"

command -v rclone >/dev/null 2>&1 || {
  echo "ERROR: rclone is not installed. Install it and run: rclone config" >&2
  exit 1
}

mkdir -p "$LOCAL_DATA_DIR"
filter_file="$(mktemp)"
trap 'rm -f "$filter_file"' EXIT

cat > "$filter_file" <<'FILTER'
+ /manifests/**
+ /normalized/**
+ /nswgov_df.csv
+ /rentboard_df.csv
- *
FILTER

echo "Pulling current data from ${REMOTE}:${DRIVE_BASE}/current -> ${LOCAL_DATA_DIR}"
rclone copy "${REMOTE}:${DRIVE_BASE}/current" "$LOCAL_DATA_DIR" --filter-from "$filter_file" --progress

echo "Done."
