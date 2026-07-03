#!/usr/bin/env bash
set -euo pipefail

REMOTE="${RCLONE_REMOTE:-gdrive}"
DRIVE_BASE="${PROPERTYIQ_GDRIVE_PATH:-propertyiq_getdata/data}"
LOCAL_DATA_DIR="${PROPERTYIQ_LOCAL_DATA_DIR:-data}"
CURRENT="${REMOTE}:${DRIVE_BASE}/current"
PREVIOUS="${REMOTE}:${DRIVE_BASE}/previous"

command -v rclone >/dev/null 2>&1 || {
  echo "ERROR: rclone is not installed. Install it and run: rclone config" >&2
  exit 1
}

for file in manifests/nswgov_sales_manifest.csv manifests/rentboard_lodgements_manifest.csv; do
  if [[ ! -f "${LOCAL_DATA_DIR}/${file}" ]]; then
    echo "ERROR: missing ${LOCAL_DATA_DIR}/${file}" >&2
    exit 1
  fi
done

filter_file="$(mktemp)"
trap 'rm -f "$filter_file"' EXIT

cat > "$filter_file" <<'FILTER'
+ /manifests/**
+ /normalized/**
+ /nswgov_df.csv
+ /rentboard_df.csv
- *
FILTER

echo "Ensuring Drive folders exist under ${REMOTE}:${DRIVE_BASE}"
rclone mkdir "$CURRENT"
rclone mkdir "$PREVIOUS"

echo "Replacing the one previous backup with the current Drive data"
rclone delete "$PREVIOUS" --filter-from "$filter_file" --progress
rclone copy "$CURRENT" "$PREVIOUS" --filter-from "$filter_file" --progress

echo "Replacing current Drive data with local refreshed data"
rclone delete "$CURRENT" --filter-from "$filter_file" --progress
rclone copy "$LOCAL_DATA_DIR" "$CURRENT" --filter-from "$filter_file" --progress

echo "Verifying Drive folders"
rclone lsf "$CURRENT" --filter-from "$filter_file"
rclone lsf "$PREVIOUS" --filter-from "$filter_file"

echo "Done."
