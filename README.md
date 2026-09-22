# propertyiq_getdata

ETL for NSW property data and Australian economic series, landed in the central Postgres:

- NSW Valuer General property sales (`nswgov`)
- NSW rental bond lodgements (`rentboard`)
- ABS Census General Community Profile, by postcode (`abs`)
- ABS economic time series — dwelling values and prices, CPI, labour force,
  wages, housing lending, building approvals, population — every state +
  Australia, full history (`abs_ts`)
- RBA interest rates — cash rate, mortgage/lending rates, rate decisions (`rba`)

This repo fetches public source files and writes normalized, period-partitioned
CSV outputs. Downstream cleaning, joining, and database loading belongs in the
separate database project.

## Data Contract

Primary outputs:

```text
data/
  normalized/
    nswgov/sales/period=YYYYMMDD.csv
    rentboard/lodgements/year=YYYY/month=MM.csv
    abs/poa/census_year=YYYY.csv           # one row per postcode, full GCP table set
    abs/poa/census_year=YYYY_columns.csv   # column -> table/short-code/long-label dictionary
    abs_ts/<dataset>/asof=YYYY-MM-DD.csv   # one snapshot per release; full history, all regions
    rba/<dataset>/asof=YYYY-MM-DD.csv
  manifests/
    nswgov_sales_manifest.csv
    rentboard_lodgements_manifest.csv
    abs_poa_manifest.csv
    abs_ts_manifest.csv
    rba_manifest.csv
```

`abs_ts` and `rba` share one long-format schema (one row per series and
period): `source, dataset, series_id, series_label, dataflow, freq,
time_period, period_start, value, unit, unit_mult, obs_status, obs_comment,
region, base_period, asof`, plus `dim_*` code/label columns for the ABS
dimensions. Because the ABS revises history, each release is a new `asof=`
snapshot rather than an edit; take `max(asof)` per series downstream.

Manifest columns:

```text
source,dataset,period_start,period_end,path,rows,sha256,created_at_utc
```

Legacy compatibility exports are available, but are no longer the primary
pipeline output:

```text
data/nswgov_df.csv
data/rentboard_df.csv
```

## Setup

This project is managed with [uv](https://docs.astral.sh/uv/). One command
creates the virtualenv (Python pinned by `.python-version`), installs the
package plus its dependencies, and includes the dev tools:

```bash
uv sync
```

By default the pipeline uses repo-local `data/`. Override it with `--data-dir`,
`PROPERTYIQ_DATA_DIR`, or `DATA_DIR`.

## Run

`uv run` executes inside the project environment. The CLI is available as the
`propertyiq-getdata` console script (equivalently `python -m propertyiq_getdata`):

```bash
uv run propertyiq-getdata nswgov update --data-dir data
uv run propertyiq-getdata rentboard update --data-dir data
uv run propertyiq-getdata audit --data-dir data
uv run pytest
```

If you are migrating a checkout that only has the old giant CSVs:

```bash
uv run propertyiq-getdata nswgov migrate-legacy --data-dir data
uv run propertyiq-getdata rentboard migrate-legacy --data-dir data
```

The monolith CSVs (`export-legacy`) are a legacy shape kept for backwards
compatibility only. The supported feed for other apps is the central Postgres.

## Central Postgres

`db` lands every manifest partition in database `propertyiq` on the
[nmp-central-ai](../nmp-central-ai/PLATFORM.md) Postgres and builds a clean,
typed **`staging`** layer with dbt. Apps import it over `postgres_fdw` and build
their own marts; this repo publishes no marts (plan
`.lavish/s03_db-pipeline-dbt-central-postgres-plan.html`).

| schema | tables | note |
|---|---|---|
| `raw` | `nswgov_sales`, `rentboard_lodgements`, `abs_ts_<dataset>` ×8, `rba_<table>` ×3 | verbatim text landing + `_partition/_sha256/_loaded_at`; owner only |
| `staging` | `property_sales`, `property_rent`, `econ_series`, `econ_series_vintages`, `econ_headline_series`, `geo_postcode` | the consumer contract; readable by `propertyiq_ro` |
| `meta` | `load_state`, `pipeline_runs` | what is loaded, when, from which sha256 |

```bash
make -C ../nmp-central-ai db-init                 # once: role + database from registry/projects.yaml (P7)
make -C ../nmp-central-ai db-urls                 # copy the P7 block into ./.env
uv sync --extra db
uv run --env-file .env propertyiq-getdata db init             # once
uv run --env-file .env propertyiq-getdata db update --data-dir data
```

`db update` is incremental (only partitions whose manifest sha256 changed are
copied), takes about a minute for the full 6.6 M rows, and records itself in
`meta.pipeline_runs`. Browse the result in DbGate (`make -C ../nmp-central-ai
db-ui`, http://127.0.0.1:5050, connection `propertyiq`). Details in AGENTS.md.

## Publishing to Databricks

The sibling `databricks-propertyiq` project reads Parquet from a Unity Catalog
volume. `publish databricks` converts new or changed partitions to Parquet and
uploads them:

```bash
uv run propertyiq-getdata publish databricks --dry-run   # print the plan only
uv run propertyiq-getdata publish databricks             # upload the delta
```

The landing contract, which the consumer depends on:

```
/Volumes/workspace/propertyiq/propertyiq/landing/
  sales/period=YYYYMMDD_<sha8>.parquet
  lodgements/month=YYYY-MM_<sha8>.parquet
```

Each file is one partition, named for the first eight hex characters of that
partition's sha256 as recorded in `data/manifests/*.csv`. Two consequences:

- **The publish is stateless.** The name encodes the content, so the set of
  names to upload is a plain set difference against the volume listing. There is
  no watermark or state file, and re-running uploads nothing.
- **Landing is append-only.** A rewritten partition — rentboard rewrites its
  trailing month on every run — uploads as a *new* file beside the old one.
  Nothing is ever overwritten or deleted, because Auto Loader tracks files
  exactly-once and never re-reads a changed one. The consumer's silver layer
  picks the newest file per partition.

Every business column is written as a `string`, matching the `FINAL_COLUMNS`
contract pinned by `tests/test_contract_outputs.py`; the consumer types in one
tested place. Auth reuses a `~/.databrickscfg` profile (`--profile`, default
`DEFAULT`) — no credential is ever read, printed, or stored by this repo.

To run one full cycle across both consumers — scrape, rebuild manifests, export
the monolith CSVs, publish the Parquet delta, then verify:

```bash
scripts/refresh_dual_pipeline.sh              # full cycle, idempotent
scripts/refresh_dual_pipeline.sh --dry-run    # show what would happen
```

A publish converts partitions in a temp dir and deletes it after upload, so
nothing is left on disk to inspect afterwards — use `scripts/inspect_parquet.py`
to look at what was actually sent.

**Publishing starts the Databricks job.** The medallion job in
`databricks-propertyiq` carries a file-arrival trigger on `landing/`, so it
launches itself roughly a minute after the last file lands, at most once every
five minutes. Nothing needs to run it by hand, and only a change to the pipeline
*code* needs a deploy (`make ship` there). On a loop this also means unattended
job runs — and unattended compute — whenever there is genuinely new data.

## Source Stages

NSW Gov still has explicit pull/extract/transform stages:

```bash
uv run propertyiq-getdata nswgov pull --data-dir data
uv run propertyiq-getdata nswgov extract --data-dir data
uv run propertyiq-getdata nswgov transform --data-dir data
```

Rentboard is self-contained:

```bash
uv run propertyiq-getdata rentboard update --data-dir data
```

ABS is a rare, manual-trigger job (Census data refreshes every ~5 years, not
weekly) but has the same explicit stages:

```bash
uv run propertyiq-getdata abs pull --data-dir data --census-year 2021 --state NSW
uv run propertyiq-getdata abs extract --data-dir data --census-year 2021 --state NSW
uv run propertyiq-getdata abs transform --data-dir data --census-year 2021 --state NSW
# or, all three:
uv run propertyiq-getdata abs update --data-dir data --census-year 2021 --state NSW
```

ABS time series and RBA tables are pulled in full every run (they are small)
and a new snapshot is written only when the content changed:

```bash
uv run propertyiq-getdata abs-ts update --data-dir data                       # 8 datasets, ~12 s
uv run propertyiq-getdata rba update --data-dir data                          # 3 tables
uv run propertyiq-getdata abs-ts update --data-dir data --dataset cpi --force  # one dataset, re-download
uv run propertyiq-getdata abs-ts pull --data-dir data --dry-run               # show the URLs
```

| dataset | upstream | headline series | history |
|---|---|---|---|
| `dwelling_values` | ABS `RES_DWELL_ST` | Total Value of Dwellings: mean price, stock value, dwelling count by state | 2011-Q3 → |
| `dwelling_medians` | ABS `RES_DWELL` | median house / unit price and transfers by capital city and rest-of-state | 2002-Q1 → |
| `cpi` | ABS `CPI` | all-groups index and % changes, 8 capitals + AUS, quarterly and monthly | 1948-Q3 → |
| `labour_force` | ABS `LF` | employed, unemployed, unemployment rate, participation rate; SA + trend; by state | 1978-02 → |
| `wpi` | ABS `WPI` | wage price index, by state | 1997-Q3 → |
| `lending_housing` | ABS `LEND_HOUSING` | new housing loan commitments, owner-occupier / investor / first home buyer, by state | 2002-Q3 → |
| `building_approvals` | ABS `BA_SA2` ×3 | new dwelling units approved by building type, by state | 2011-07 → |
| `population` | ABS `ERP_Q` | estimated resident population and annual % change, by state | 1981-Q3 → |
| `rba_cash_rate` | RBA F1.1 | cash rate target, interbank overnight, bank bills | 1969-06 → |
| `rba_lending_rates` | RBA F5 | housing variable / fixed rates, owner-occupier vs investor; business; personal | 1959-01 → |
| `rba_rate_changes` | RBA A2 | every cash rate decision as announced | 1990-01 → |

### How NSW Gov archives are found

The Valuer General retired the portal page this scraper used to parse, and the
bulk archives now live at a predictable address:

```
https://www.valuergeneral.nsw.gov.au/__psi/weekly/YYYYMMDD.zip   # Mondays
https://www.valuergeneral.nsw.gov.au/__psi/yearly/YYYY.zip
```

Two properties of that host shape how `pull` works:

- **There is no listing to scrape** — the directory index returns 403. Periods
  are enumerated locally (`candidate_links`) and confirmed with one HEAD each
  (`probe_links`); a period that has not been published yet answers 404, which
  is how the scan finds the end of the data. A routine run only probes the few
  periods after the watermark, not all 750 Mondays since 2012.
- **A WAF rejects non-browser TLS handshakes.** Plain `requests` gets 403 on a
  file a browser downloads fine, whatever headers it sends, so transfers use
  `curl_cffi` impersonating Chrome. This is a TLS-fingerprint problem, not a
  JavaScript one — no headless browser is involved.

Probing is deliberately **sequential**. Under concurrent load the host starts
answering 404 for files that plainly exist, and a rate-limit 404 is
indistinguishable from "not published yet", so fanning out risks silently
skipping a week of sales. A transport error is never read as absent either — it
raises `ProbeError` after retries rather than quietly shrinking the result.

## Maintenance

Each source can rebuild its manifest from the partitions already on disk, without
re-scraping — useful for recovery if a manifest is lost or after hand-editing
partitions:

```bash
uv run propertyiq-getdata nswgov manifest --data-dir data
uv run propertyiq-getdata rentboard manifest --data-dir data
uv run propertyiq-getdata abs manifest --data-dir data
```

## Google Drive Storage

Data CSVs are ignored by git and stored in Google Drive. The Drive data contract
now syncs `normalized/`, `manifests/`, and the optional legacy CSVs.

Configure `rclone` once:

```bash
brew install rclone
rclone config
scripts/google_drive_check.sh
```

Pull before local work:

```bash
scripts/data_pull.sh
```

Refresh, test, and push:

```bash
scripts/update_data_and_push.sh
```

## Project Layout

The implementation is a single package, organized by responsibility:

```text
propertyiq_getdata/
├── cli.py, __main__.py    # command-line entrypoint (python -m propertyiq_getdata)
├── core/                  # reusable pipeline mechanics, source-agnostic
│   ├── paths.py           #   data-dir + partition path resolution
│   ├── manifest.py        #   manifest schema + writer
│   ├── io.py              #   atomic CSV writes
│   ├── snapshot.py        #   asof= snapshots with content-hash dedupe
│   └── series.py          #   long-format contract shared by abs_ts + rba
├── sources/               # one cohesive module per collected source
│   ├── nswgov.py          #   NSW Valuer General property sales
│   ├── rentboard.py       #   NSW rental bond lodgements
│   ├── abs.py             #   ABS Census GCP DataPack, by postcode (POA)
│   ├── abs_ts.py          #   ABS Data API time series (SDMX)
│   └── rba.py             #   RBA statistical tables (interest rates)
├── sinks/                 # one module per publish target (counterpart of sources/)
│   └── databricks.py      #   updates-only Parquet -> Unity Catalog volume
├── db/                    # central Postgres: manifests -> raw (COPY), dbt -> staging
├── audit.py               # cross-source output summary / integrity check
└── diagnostics.py         # ad-hoc comparison/analysis helpers
dbt/                       # dbt project: staging models, seeds, tests
tests/                     # contract + per-source regression tests
scripts/                   # Drive sync, update-and-push, econ headline seed
```

Sources pull data in and write canonical CSV partitions; sinks take those
partitions and publish them somewhere else. Add a new source by dropping a
module into `sources/` modelled on `nswgov.py` (shared mechanics come from
`core/`), then wiring its subcommands into `cli.py`. There are no per-stage
folders — a source's pull/extract/transform steps are functions inside its own
module, and are exposed as CLI subcommands.

Downstream consumers:

| Consumer | Feed | Pipeline |
|---|---|---|
| `data-qa-agent` | `propertyiq.staging` over `postgres_fdw` | its own dbt marts + RLS in database `dataqa` |
| `databricks-propertyiq` (ended) | Parquet via `publish databricks` | Auto Loader → bronze/silver/gold |

## Archived Code

Historical, unmaintained code (the old REA / Domain / auhouse scrapers, the
`etl4_load` master build, the Flask scaffold, and ad-hoc analysis) lives in
[`archive/`](./archive/README.md). It is kept only as reference for reviving a
source later and is not part of the active pipeline. See `AGENTS.md` for the full
guide.
