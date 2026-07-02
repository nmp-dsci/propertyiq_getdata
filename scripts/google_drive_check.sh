#!/usr/bin/env bash
set -euo pipefail

REMOTE="${RCLONE_REMOTE:-gdrive}"
DRIVE_BASE="${PROPERTYIQ_GDRIVE_PATH:-propertyiq_getdata/data}"

command -v rclone >/dev/null 2>&1 || {
  echo "ERROR: rclone is not installed. On macOS run: brew install rclone" >&2
  exit 1
}

if ! rclone listremotes | grep -qx "${REMOTE}:"; then
  cat >&2 <<EOF
ERROR: rclone remote '${REMOTE}' is not configured.

Run:
  rclone config

Recommended answers:
  n) New remote
  name> ${REMOTE}
  Storage> drive
  scope> drive
  root_folder_id> leave blank
  service_account_file> leave blank
  Edit advanced config? n
  Use auto config? y

Then rerun:
  scripts/google_drive_check.sh
EOF
  exit 1
fi

echo "Remote '${REMOTE}' exists."
echo "Checking Drive path ${REMOTE}:${DRIVE_BASE}"
rclone mkdir "${REMOTE}:${DRIVE_BASE}/current"
rclone mkdir "${REMOTE}:${DRIVE_BASE}/previous"
rclone lsf "${REMOTE}:${DRIVE_BASE}" || true
echo "Google Drive data path is ready."
