#!/usr/bin/env bash
set -euo pipefail

# Ensure the project environment is in sync before running the pipeline.
# `--extra db` brings psycopg + dbt for the central-Postgres stage at the end.
uv sync --extra db

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
# Economic time series: cheap (a dozen small requests) and self-deduplicating --
# a new snapshot appears only when the ABS / RBA actually released something.
uv run propertyiq-getdata abs-ts update --data-dir data
uv run propertyiq-getdata rba update --data-dir data
uv run pytest

# Central Postgres (nmp-central-ai, database `propertyiq`): manifests -> raw,
# dbt -> staging. Incremental: only partitions whose sha256 changed are copied.
# Needs the P7 block of nmp-central-ai/.db-urls.env in ./.env (see AGENTS.md).
uv run --env-file .env propertyiq-getdata db update --data-dir data

# Google Drive copy of the legacy monoliths. Kept until data-qa-agent's
# cut-over to propertyiq_staging (plan s03, P6) lands; then remove.
scripts/data_push_with_one_backup.sh
