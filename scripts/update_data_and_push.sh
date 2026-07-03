#!/usr/bin/env bash
set -euo pipefail

# Ensure the project environment is in sync before running the pipeline.
uv sync

uv run propertyiq-getdata nswgov pull --data-dir data
uv run propertyiq-getdata nswgov extract --data-dir data
if [[ -f data/nswgov_df.csv && ! -f data/manifests/nswgov_sales_manifest.csv ]]; then
  uv run propertyiq-getdata nswgov migrate-legacy --data-dir data
fi
uv run propertyiq-getdata nswgov transform --data-dir data
if [[ -f data/rentboard_df.csv && ! -f data/manifests/rentboard_lodgements_manifest.csv ]]; then
  uv run propertyiq-getdata rentboard migrate-legacy --data-dir data
fi
uv run propertyiq-getdata rentboard update --data-dir data
uv run pytest

scripts/data_push_with_one_backup.sh
