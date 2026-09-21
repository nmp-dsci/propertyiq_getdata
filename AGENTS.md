# AGENTS.md — propertyiq_getdata

Collection-only ETL for NSW property data sources. It fetches public source
files, normalizes each new period independently, and writes period-partitioned
CSVs plus manifests. **Downstream cleaning, joining, and database loading belongs
in the separate database project — not here.**

> **Actively maintained:** the `propertyiq_getdata/` package (the `nswgov`,
> `rentboard`, `abs`, `abs_ts` and `rba` sources). Everything historical (old REA/Domain/auhouse
> scrapers, the master-build stage, the Flask scaffold, ad-hoc analysis) has been
> moved to [`archive/`](./archive/README.md) as unmaintained reference. Do not
> wire `archive/` into the live pipeline.

---

## Layout

The code is one package, organized by responsibility — **not** by ETL stage.
Each source is cohesive in a single module under `sources/`; the reusable,
source-agnostic mechanics live under `core/`. Changing one source touches one
file.

```
propertyiq_getdata/          # the package — the pipeline
├── __main__.py, cli.py      # `python -m propertyiq_getdata ...` (thin: parse -> dispatch)
├── core/                    # reusable pipeline mechanics, source-agnostic
│   ├── paths.py             #   data-dir resolution + partition paths
│   ├── manifest.py          #   manifest schema + writer
│   ├── io.py                #   atomic_write_csv (temp-then-replace)
│   ├── snapshot.py          #   asof=YYYY-MM-DD snapshots, content-hash dedupe (abs_ts, rba)
│   └── series.py            #   long-format contract shared by abs_ts + rba (CORE_COLUMNS)
├── sources/                 # one module per source; pull/extract/transform are functions here
│   ├── nswgov.py            #   NSW Valuer General property sales
│   ├── rentboard.py         #   NSW rental bond lodgements
│   ├── abs.py               #   ABS Census GCP DataPack, by postcode (POA)
│   ├── abs_ts.py            #   ABS Data API time series (dwellings, CPI, labour, wages, lending, approvals, ERP)
│   └── rba.py               #   RBA statistical tables (cash rate, lending rates, rate changes)
├── sinks/                   # one module per publish target (counterpart of sources/)
│   └── databricks.py        #   updates-only Parquet -> Unity Catalog volume
├── audit.py                 # cross-source output summary / integrity check
└── diagnostics.py           # ad-hoc comparison/analysis helpers
tests/                       # contract + per-source regression tests
scripts/                     # rclone Drive sync, update-and-push, dual-pipeline refresh, Parquet inspection
archive/                     # historical, unmaintained code — see archive/README.md
```

Public API (`propertyiq_getdata/__init__.py`) re-exports the stable entrypoints:
`update_nswgov`, `update_rentboard`, `audit_outputs`, `print_audit`. Source
internals are imported from `propertyiq_getdata.sources.<name>`; shared mechanics
from `propertyiq_getdata.core.<name>`.

## Data contract

Primary outputs (all under the resolved data dir; git-ignored, stored in Drive):

```text
data/normalized/nswgov/sales/period=YYYYMMDD.csv
data/normalized/rentboard/lodgements/year=YYYY/month=MM.csv
data/normalized/abs/poa/census_year=YYYY.csv           # one row per postcode, full GCP table set
data/normalized/abs/poa/census_year=YYYY_columns.csv   # column -> table/short-code/long-label dictionary
data/normalized/abs_ts/<dataset>/asof=YYYY-MM-DD.csv     # one snapshot per release, full history, all regions
data/normalized/rba/<dataset>/asof=YYYY-MM-DD.csv
data/manifests/nswgov_sales_manifest.csv
data/manifests/rentboard_lodgements_manifest.csv
data/manifests/abs_poa_manifest.csv
data/manifests/abs_ts_manifest.csv                        # one manifest per source; `dataset` column varies
data/manifests/rba_manifest.csv
```

Manifest columns: `source, dataset, period_start, period_end, path, rows, sha256, created_at_utc`.
For snapshot sources `period_start`/`period_end` are the min/max observation
period inside that snapshot, and the vintage is in the path.

Legacy monolith CSVs (`data/nswgov_df.csv`, `data/rentboard_df.csv`) are optional
compatibility exports only, produced on demand by `export-legacy`.

The data dir is resolved by `paths.resolve_data_dir`: explicit `--data-dir` >
`PROPERTYIQ_DATA_DIR` > `DATA_DIR` > repo-local `data/`.

Two downstream consumers read these outputs, and neither is legacy:

| Consumer | Feed | Pipeline |
|---|---|---|
| `data-qa-agent` | monolith CSVs via `export-legacy` | dlt → dbt → Postgres marts |
| `databricks-propertyiq` | Parquet via `publish databricks` (below) | Auto Loader → bronze/silver/gold |

## The sources

**nswgov** — NSW Valuer General property sales.
Source: https://www.valuergeneral.nsw.gov.au/__psi/{weekly/YYYYMMDD,yearly/YYYY}.zip
(see "How NSW Gov archives are found" in the README for why discovery is
enumerate-and-probe rather than scraping a listing).
`.DAT` file format spec: https://www.valuergeneral.nsw.gov.au/__data/assets/pdf_file/0015/216402/Current_Property_Sales_Data_File_Format_2001_to_Current.pdf
Explicit stages, all incremental/idempotent:

| Stage | Function | In → Out |
|-------|----------|----------|
| pull | `pull_nswgov` | Enumerates `yearly` (`YYYY.zip`) and `weekly` (`YYYYMMDD.zip`) candidates (`candidate_links`), confirms each with a HEAD (`probe_links`), downloads & unzips new periods into `data/raw/nswgov/...`. |
| extract | `extract_nswgov` | Parses `;`-delimited `.DAT` (record types A/B/C/D via `nswgov_dat_map`), melts to long form, writes one CSV per period to `data/interim/nswgov/output_etl2/`. |
| transform | `transform_nswgov` | Keeps record_type `B`, pivots labels to `FINAL_COLUMNS`, writes `normalized/nswgov/sales/period=YYYYMMDD.csv` (atomic temp-then-replace) and refreshes the manifest. |

**rentboard** — NSW rental bond lodgements. Self-contained `update_rentboard`:
scrapes `.xlsx` links, classifies annual vs monthly by title regex, prefers
monthly when a year has months, normalizes to `FINAL_COLUMNS`, and writes/merges
`normalized/rentboard/lodgements/year=YYYY/month=MM.csv` + manifest.
Source: https://www.nsw.gov.au/housing-and-construction/rental-forms-surveys-and-data/rental-bond-data

**abs** — ABS Census General Community Profile (GCP), by postcode (`POA`
geography). Postcode was chosen as the only ABS geography that joins onto both
`nswgov` (`postcode`) and `rentboard` (`postcode` — it has no suburb field);
`SAL` (suburb) and `LGA` (council) are deliberately out of scope. Explicit
stages, idempotent per `(census_year, state, geography)`:

| Stage | Function | In → Out |
|-------|----------|----------|
| pull | `pull_abs` | Downloads the GCP DataPack ZIP (`.../datapacks/download/{year}_GCP_{geography}_for_{state}_short-header.zip`) and unzips into `data/raw/abs/{year}/{geography}/{state}/`. Skips if already extracted; `--force` re-downloads. |
| extract | `extract_abs` | For every `{year}Census_G##_{state}_{geography}.csv` table file present (not a hardcoded table list — the DataPack ships ~119 tables), converts `POA_CODE_YYYY` (e.g. `POA2000`) to a zero-padded `postcode`, writes one interim CSV per table to `data/interim/abs/{year}/{state}_{geography}/`. |
| transform | `transform_abs` | Merges every table on `postcode` into one wide row per postcode, namespacing columns as `{table}__{short_code}` (~415 short codes collide across tables in the real 2021 DataPack, e.g. `Tot_P`/`Tot_M`/`Tot_F`, so this is not optional). Writes `normalized/abs/poa/census_year={year}.csv`, a companion `..._columns.csv` decoding each column to its long label/table name (from the DataPack's `Metadata_*.xlsx`), and refreshes the manifest. |

Source: https://www.abs.gov.au/census/find-census-data/datapacks (2021 Census
General Community Profile). Unlike `nswgov`/`rentboard`, this is not a weekly
scrape — Census data refreshes roughly every 5 years, so `abs update` is a rare,
manual-trigger job. The output is intentionally wide (~17,000 columns for the
full 2021 GCP table set) rather than curated, so the column set is derived from
the DataPack's own metadata workbook at extract/transform time instead of a
hand-maintained `FINAL_COLUMNS` list — a future Census release with
renumbered/added tables needs no code changes, just a re-run.

**abs_ts** — ABS economic *time series* via the ABS Data API (SDMX 2.1 REST,
`https://data.api.abs.gov.au/rest/data/ABS,{dataflow}/{key}`, CSV with
`labels=both`, no auth). Not the Census. A curated registry `SERIES` maps each
dataset to one SDMX key (headline measures only) applied to one or more
dataflows; **REGION is never filtered** (every state/territory + AUS, all
capital cities/GCCSAs) and **`startPeriod` is never sent** (full history —
CPI from 1948, LF from 1978), both pinned by tests. Two stages, idempotent per
`(dataset, asof)`:

| Stage | Function | In → Out |
|-------|----------|----------|
| pull | `pull_abs_ts` | One GET per dataflow, response saved verbatim to `raw/abs_ts/<dataset>/asof=YYYY-MM-DD__<DATAFLOW>.csv`. Skips if present; `--force` re-downloads. A 404 whose body is `NoRecordsFound` is the zero-rows signal and raises `NoRecordsError`. |
| transform | `transform_abs_ts` | `parse_sdmx_csv` splits every `"code: label"` dimension into `dim_<NAME>` + `dim_<NAME>_label`, derives `series_id` (dataflow + full key), `period_start` (ISO first day: `2026-Q2` → `2026-04-01`), `region` (state names shortened via `core.series.REGION_SHORT`), keeps `base_period` (indexes get rebased). Stitched datasets (`building_approvals` = `BA_SA2_201116` + `BA_SA2_2016-21` + `BA_SA2`) are concatenated with `dataflow` kept. Writes `normalized/abs_ts/<dataset>/asof=YYYY-MM-DD.csv` **only if the content differs** from the newest snapshot (`core.snapshot.write_snapshot_if_changed`, which hashes the file ignoring the `asof` column), then refreshes the manifest. |

Datasets (2026-09-21): `dwelling_values` (RES_DWELL_ST — the "Total Value of
Dwellings" release: value of stock, dwelling count, mean price by state),
`dwelling_medians` (RES_DWELL — median house/unit price and transfer counts by
GCCSA), `cpi` (CPI, quarterly + monthly, 8 capitals + AUS), `labour_force`
(LF: employed, unemployed, unemployment rate, participation; SA + trend),
`wpi`, `lending_housing` (LEND_HOUSING, quarterly; OO / investor / FHB),
`building_approvals`, `population` (ERP_Q). `RPPI` is discontinued (2021-Q4)
and `CPI_M` ended 2025-09 (monthly CPI now lives in `CPI`) — do not add them
back to the scheduled registry. Adding a series is one `SeriesSpec` entry.

**rba** — Reserve Bank statistical tables, the source of interest rates (not
ABS). Static CSVs at `https://www.rba.gov.au/statistics/tables/csv/<table>-data.csv`,
full history included: `rba_cash_rate` (F1.1, monthly, from 1969),
`rba_lending_rates` (F5, monthly mortgage/business/personal rates, from 1959),
`rba_rate_changes` (A2, every cash-rate decision as announced, from 1990).
Same two stages and snapshot contract as `abs_ts` (`pull_rba`,
`transform_rba`). `parse_rba_csv` locates the `Title / Frequency / Units /
Series ID` header rows, keys columns by **Series ID** (titles get reworded),
melts to long form, and handles both date formats (`DD/MM/YYYY` in F1.1/F5,
`DD-MMM-YYYY` in A2); month-end dates become `period_start` = first of month;
non-numeric cells (A2's pre-1990 `"17.00 to 17.50"` ranges) keep `value` NaN
with the text in `obs_comment`. Needs a browser-like `User-Agent`.

Both sources write the **same long-format contract** (`core/series.py`):
`CORE_COLUMNS` = `source, dataset, series_id, series_label, dataflow, freq,
time_period, period_start, value, unit, unit_mult, obs_status, obs_comment,
region, base_period, asof`, followed by any `dim_*` columns (ragged across
datasets; RBA has none). Downstream should take `max(asof)` per series —
revisions and rebases produce a new vintage, never an edit of an old one.

## Publishing to Databricks

`sinks/databricks.py` (`publish_databricks`, CLI: `publish databricks`) converts
new or changed partitions to Parquet and uploads them to a Unity Catalog volume
for `databricks-propertyiq`'s Auto Loader pipeline to ingest:

```text
/Volumes/workspace/propertyiq/propertyiq/landing/
  sales/period=YYYYMMDD_<sha8>.parquet
  lodgements/month=YYYY-MM_<sha8>.parquet
```

Planning and Parquet conversion are pure functions; only `VolumeSink` touches
the network, and it is injected, so the tests in
`tests/test_publish_databricks.py` run offline against a fake sink.

- **Stateless.** Each file is named `<partition>_<sha8>.parquet` from the
  partition's sha256 already recorded in `data/manifests/*.csv`, so the set of
  names to upload is a plain set difference against the volume listing — no
  watermark, no state file.
- **Append-only by design.** A rewritten partition (rentboard rewrites its
  trailing month every run) uploads as a *new* file beside the old one; nothing
  is overwritten or deleted (`overwrite=False`). Auto Loader tracks files
  exactly-once and never re-reads a changed file, so the consumer's silver
  layer picks the newest file per partition.
- **Every business column is a string**, matching the `FINAL_COLUMNS` contract
  pinned by `tests/test_contract_outputs.py`; the consumer types once, in one
  tested place, because the sales data carries three numeric encodings across
  its history. `keep_default_na=False` on read keeps empty string as empty
  string instead of becoming NaN/NULL.
- Auth reuses a `~/.databrickscfg` profile via `--profile` (default `DEFAULT`);
  no credential is read, printed, or stored — this repo is public.
- `scripts/inspect_parquet.py` inspects what was actually uploaded: a publish
  converts to a temp dir and deletes it after upload, so nothing is left on
  disk to look at otherwise.
- `scripts/refresh_dual_pipeline.sh` runs one idempotent cycle across both
  consumers: scrape, rebuild manifests, export the monolith CSVs, publish the
  Parquet delta, then verify.

## Running

Managed with **uv**. `uv sync` builds the env (Python from `.python-version`,
package installed editable, dev tools included); `uv run` executes in it. The CLI
is the `propertyiq-getdata` console script (or `python -m propertyiq_getdata`).

```bash
uv sync
uv run propertyiq-getdata nswgov update --data-dir data
uv run propertyiq-getdata rentboard update --data-dir data
uv run propertyiq-getdata abs update --data-dir data --census-year 2021 --state NSW
uv run propertyiq-getdata abs-ts update --data-dir data            # all 8 datasets, ~12 s
uv run propertyiq-getdata rba update --data-dir data
uv run propertyiq-getdata abs-ts update --data-dir data --dataset cpi --dataset labour_force --force
uv run propertyiq-getdata audit --data-dir data
uv run pytest            # offline; `uv run pytest -m live` also hits the ABS API once
```

Migration/compat: `nswgov|rentboard migrate-legacy` splits an old monolith CSV
into partitions; `export-legacy` stacks partitions back into the monolith shape;
`nswgov manifest` / `rentboard manifest` / `abs manifest` / `abs-ts manifest` /
`rba manifest` rebuild a manifest from partitions.

Dependencies are declared in `pyproject.toml` and pinned in `uv.lock` (commit
both). Runtime: `beautifulsoup4, pandas, numpy, requests, curl-cffi, openpyxl`
(+ `matplotlib` for `diagnostics.py`, `databricks-sdk` + `pyarrow` for
`sinks/databricks.py`); dev group: `pytest`. Add one with `uv add <pkg>` (or
`uv add --dev <pkg>`). Note: the old `stem`/Tor dependency was only used by
`archive/` and is no longer installed.

## Conventions & gotchas

- Every stage is **incremental/idempotent** — it detects already-processed
  periods (via the manifest, then partitions, then a legacy CSV) and skips them.
  The "latest period" logic lives in `latest_final_period` (nswgov) and
  `latest_lodgement_dt` (rentboard).
- Stages **raise on zero rows** (`ZERO rows added ... investigate`) — that is the
  signal the source layout changed and a scraper needs updating.
- **Site-layout changes are the usual break point.** nswgov depends on the
  `__psi` archive URL shape and Monday-dated weekly periods (`candidate_links`,
  `probe_links`); rentboard depends on link title regexes (`MONTH_PATTERN`, the
  year regex) and the xlsx header row (`read_excel(header=2)`) + expected
  `XLSX_COLUMNS`. Update these when a probe/scrape returns nothing. abs_ts
  depends on each registry key having exactly the DSD's dimension count
  (`tests/test_abs_ts_pipeline.py::DSD_DIMENSIONS`) — a 404 `NoRecordsFound`
  usually means a dataflow was re-versioned or a code retired; check
  `/rest/dataflow/ABS/<ID>?references=all`. rba depends on the `Series ID`
  header row and the two date formats in `sources/rba.py`.
  `discover_links` (the old listing-page parser) is kept and tested but is no
  longer on the live `pull_nswgov` path.
- **nswgov probing is deliberately sequential** (`probe_links` defaults to
  `workers=1`) — see the README section above for why concurrent HEADs produce
  false 404s on this host. A transport error raises `ProbeError` rather than
  being treated as "not published".
- **abs (Census) break point:** depends on the DataPack download URL shape
  (`datapack_zip_url`) and the `Metadata_*.xlsx` sheet names/header rows
  (`_header_and_rows`) — check both if a future Census release's DataPack layout
  changes.
- Partition writes are **atomic** (write `.csv.tmp`, then `Path.replace`), so an
  interrupted run never leaves a half-written partition.
- **Snapshot sources never edit history.** `abs_ts`/`rba` dedupe on content
  (ignoring `asof`), so a rerun on a quiet week writes nothing and a release
  adds one file per changed dataset. Same-day reruns after a code fix report
  `rewritten`. Raw API responses are kept verbatim, so a parse bug is fixed by
  re-running `transform`, never by re-hitting the API.
- After changing output shape, update the tests in `tests/` — they pin the
  partition naming, schemas, and manifest columns.

## Reviving a historical source

See [`archive/README.md`](./archive/README.md). Copy the `nswgov`/`rentboard`
module shape into a new `propertyiq_getdata/<source>.py`; do not port the old
`/Users/macmac/...` paths, `from config import *`, or Tor plumbing.
