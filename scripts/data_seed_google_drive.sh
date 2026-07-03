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

latest_backup_dir="$(find "${LOCAL_DATA_DIR}/backups" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort | tail -n 1 || true)"
if [[ -z "$latest_backup_dir" ]]; then
  echo "ERROR: no local backup directory found under ${LOCAL_DATA_DIR}/backups" >&2
  exit 1
fi

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

echo "Seeding Drive current from ${LOCAL_DATA_DIR}"
rclone mkdir "$CURRENT"
rclone delete "$CURRENT" --filter-from "$filter_file" --progress
rclone copy "$LOCAL_DATA_DIR" "$CURRENT" --filter-from "$filter_file" --progress

echo "Seeding Drive previous from ${latest_backup_dir}"
rclone mkdir "$PREVIOUS"
rclone delete "$PREVIOUS" --filter-from "$filter_file" --progress
rclone copy "$latest_backup_dir" "$PREVIOUS" --filter-from "$filter_file" --progress

echo "Current:"
rclone lsf "$CURRENT" --filter-from "$filter_file"
echo "Previous:"
rclone lsf "$PREVIOUS" --filter-from "$filter_file"

echo "Done."
