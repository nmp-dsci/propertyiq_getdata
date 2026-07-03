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

If a downstream job still needs the old files during transition:

```bash
uv run propertyiq-getdata nswgov export-legacy --data-dir data
uv run propertyiq-getdata rentboard export-legacy --data-dir data
```

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
├── audit.py               # cross-source output summary / integrity check
└── diagnostics.py         # ad-hoc comparison/analysis helpers
tests/                     # contract + per-source regression tests
scripts/                   # rclone Drive sync + update-and-push helpers
```

Add a new source by dropping a module into `sources/` modelled on `nswgov.py`
(shared mechanics come from `core/`), then wiring its subcommands into `cli.py`.
There are no per-stage folders — a source's pull/extract/transform steps are
functions inside its own module, and are exposed as CLI subcommands.

## Archived Code

Historical, unmaintained code (the old REA / Domain / auhouse scrapers, the
`etl4_load` master build, the Flask scaffold, and ad-hoc analysis) lives in
[`archive/`](./archive/README.md). It is kept only as reference for reviving a
source later and is not part of the active pipeline. See `AGENTS.md` for the full
guide.
