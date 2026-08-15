#!/usr/bin/env bash
#
# One full cycle of the dual-output pipeline: scrape whatever is new upstream,
# then feed both downstream consumers from the same canonical partitions.
#
#   CSV  path -> data/nswgov_df.csv + data/rentboard_df.csv, ingested by the
#                sibling data-qa-agent (dlt -> dbt -> Postgres marts)
#   Parquet   -> landing/ in the Unity Catalog volume, ingested by the sibling
#                databricks-propertyiq (Auto Loader -> bronze/silver/gold)
#
# Safe to run on a loop: every stage is idempotent. A second run with no new
# upstream data scrapes nothing, rewrites the same CSVs, and uploads zero
# Parquet files.
#
# Publishing is what starts the Databricks job -- the medallion job carries a
# file-arrival trigger on landing/, so it launches itself about a minute after
# the last file lands (and at most once every five minutes). Nothing here needs
# to run it, and on a loop that means unattended job runs, and therefore
# unattended compute, whenever there is genuinely new upstream data. Only a
# change to the pipeline *code* needs a deploy (`make ship` in that repo).
#
#   scripts/refresh_dual_pipeline.sh              # full cycle
#   scripts/refresh_dual_pipeline.sh --dry-run    # show what would happen
#   scripts/refresh_dual_pipeline.sh --skip-scrape  # republish existing data only
#
# Env:
#   PROPERTYIQ_PROFILE   Databricks CLI profile (default DEFAULT)
#   PROPERTYIQ_DATA_DIR  Data directory (default repo-local data/)

set -euo pipefail

cd "$(dirname "$0")/.."

PROFILE="${PROPERTYIQ_PROFILE:-DEFAULT}"
DRY_RUN=""
SKIP_SCRAPE=""

for arg in "$@"; do
  case "$arg" in
    --dry-run)      DRY_RUN="--dry-run" ;;
    --skip-scrape)  SKIP_SCRAPE="1" ;;
    -h|--help)      sed -n '2,25p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown argument: $arg" >&2; exit 2 ;;
  esac
done

run() { echo; echo "==> $*"; "$@"; }

echo "profile=$PROFILE dry_run=${DRY_RUN:-no} skip_scrape=${SKIP_SCRAPE:-no}"

# ---------------------------------------------------------------------------
# 1. Scrape. Both sources are watermark-driven, so this is a no-op when there
#    is nothing new upstream.
# ---------------------------------------------------------------------------
if [[ -z "$SKIP_SCRAPE" ]]; then
  run uv run python -m propertyiq_getdata nswgov update ${DRY_RUN}
  run uv run python -m propertyiq_getdata rentboard update ${DRY_RUN}
else
  echo "==> skipping scrape"
fi

if [[ -n "$DRY_RUN" ]]; then
  run uv run python -m propertyiq_getdata publish databricks --profile "$PROFILE" --dry-run
  echo; echo "dry run complete — nothing was written or uploaded."
  exit 0
fi

# ---------------------------------------------------------------------------
# 2. Rebuild the manifests. The sha256 per partition is what the Parquet
#    publish diffs against, so this has to happen before publishing.
# ---------------------------------------------------------------------------
run uv run python -m propertyiq_getdata nswgov manifest
run uv run python -m propertyiq_getdata rentboard manifest

# ---------------------------------------------------------------------------
# 3. CSV consumer: restack the partitions into the monolith shape data-qa-agent
#    ingests. Unchanged behaviour — this is the pre-existing path.
# ---------------------------------------------------------------------------
run uv run python -m propertyiq_getdata nswgov export-legacy
run uv run python -m propertyiq_getdata rentboard export-legacy

# ---------------------------------------------------------------------------
# 4. Parquet consumer: upload only the partitions the volume does not hold.
#    Counted before and after, because landing/ carries a file-arrival trigger:
#    an upload here is what starts the Databricks job, so whether anything
#    landed decides what to tell the operator at the end.
# ---------------------------------------------------------------------------
landing_count() {
  databricks fs ls "dbfs:/Volumes/workspace/propertyiq/propertyiq/landing/$1" \
    --profile "$PROFILE" 2>/dev/null | wc -l | tr -d ' '
}

sales_before=$(landing_count sales)
rent_before=$(landing_count lodgements)

run uv run python -m propertyiq_getdata publish databricks --profile "$PROFILE"

# ---------------------------------------------------------------------------
# 5. Prove both outputs are consistent with each other and with the volume.
# ---------------------------------------------------------------------------
run uv run python -m propertyiq_getdata audit

echo
echo "==> landing file counts vs manifest counts"
sales_remote=$(landing_count sales)
rent_remote=$(landing_count lodgements)
sales_local=$(($(wc -l < data/manifests/nswgov_sales_manifest.csv) - 1))
rent_local=$(($(wc -l < data/manifests/rentboard_lodgements_manifest.csv) - 1))

echo "    sales:      manifest=$sales_local  landing=$sales_remote"
echo "    lodgements: manifest=$rent_local  landing=$rent_remote"

# Landing is append-only, so remote >= local is correct: a revised partition
# leaves its previous version in place for the consumer to supersede.
if (( sales_remote < sales_local || rent_remote < rent_local )); then
  echo "FAIL: landing holds fewer files than the manifest — publish did not complete." >&2
  exit 1
fi

echo
if (( sales_remote > sales_before || rent_remote > rent_before )); then
  # The medallion job carries a file-arrival trigger on landing/, so publishing
  # is the trigger — nothing needs to be launched by hand. It waits 60s after
  # the last file lands and runs at most once every 5 minutes.
  echo "cycle complete — new files landed, so the Databricks job will start itself"
  echo "in about a minute (file-arrival trigger on landing/)."
  echo
  echo "Once it finishes, check gold against the dbt reference:"
  echo "  (cd ../databricks-propertyiq && make summary)   # watch the run"
  echo "  (cd ../databricks-propertyiq && uv run python scripts/parity_check.py --profile $PROFILE)"
else
  echo "cycle complete — nothing new to publish, so no Databricks run is due."
fi
echo
echo "Only pipeline *code* changes need a deploy: cd ../databricks-propertyiq && make ship"
