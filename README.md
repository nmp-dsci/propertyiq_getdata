# propertyiq_getdata

Collection-only ETL for two NSW property data sources:

- NSW Valuer General property sales (`nswgov`)
- NSW rental bond lodgements (`rentboard`)

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
  manifests/
    nswgov_sales_manifest.csv
    rentboard_lodgements_manifest.csv
```

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

The monolith CSVs are also the feed for the sibling `data-qa-agent` project,
which ingests them with dlt and builds dbt marts in Postgres:

```bash
uv run propertyiq-getdata nswgov export-legacy --data-dir data
uv run propertyiq-getdata rentboard export-legacy --data-dir data
```

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
│   └── io.py              #   atomic CSV writes
├── sources/               # one cohesive module per collected source
│   ├── nswgov.py          #   NSW Valuer General property sales
│   └── rentboard.py       #   NSW rental bond lodgements
├── sinks/                 # one module per publish target (counterpart of sources/)
│   └── databricks.py      #   updates-only Parquet -> Unity Catalog volume
├── audit.py               # cross-source output summary / integrity check
└── diagnostics.py         # ad-hoc comparison/analysis helpers
tests/                     # contract + per-source regression tests
scripts/                   # Drive sync, update-and-push, dual-pipeline refresh
```

Sources pull data in and write canonical CSV partitions; sinks take those
partitions and publish them somewhere else. Add a new source by dropping a
module into `sources/` modelled on `nswgov.py` (shared mechanics come from
`core/`), then wiring its subcommands into `cli.py`. There are no per-stage
folders — a source's pull/extract/transform steps are functions inside its own
module, and are exposed as CLI subcommands.

The two downstream consumers are fed from the same partitions and neither
format is legacy:

| Consumer | Feed | Pipeline |
|---|---|---|
| `data-qa-agent` | monolith CSVs via `export-legacy` | dlt → dbt → Postgres marts |
| `databricks-propertyiq` | Parquet via `publish databricks` | Auto Loader → bronze/silver/gold |

## Archived Code

Historical, unmaintained code (the old REA / Domain / auhouse scrapers, the
`etl4_load` master build, the Flask scaffold, and ad-hoc analysis) lives in
[`archive/`](./archive/README.md). It is kept only as reference for reviving a
source later and is not part of the active pipeline. See `AGENTS.md` for the full
guide.
