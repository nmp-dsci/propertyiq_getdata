# AGENTS.md — propertyiq_getdata

Collection-only ETL for two NSW property data sources. It fetches public source
files, normalizes each new period independently, and writes period-partitioned
CSVs plus manifests. **Downstream cleaning, joining, and database loading belongs
in the separate database project — not here.**

> **Actively maintained:** the `propertyiq_getdata/` package (the `nswgov` and
> `rentboard` sources). Everything historical (old REA/Domain/auhouse scrapers,
> the master-build stage, the Flask scaffold, ad-hoc analysis) has been moved to
> [`archive/`](./archive/README.md) as unmaintained reference. Do not wire
> `archive/` into the live pipeline.

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
│   └── io.py                #   atomic_write_csv (temp-then-replace)
├── sources/                 # one module per source; pull/extract/transform are functions here
│   ├── nswgov.py            #   NSW Valuer General property sales
│   └── rentboard.py         #   NSW rental bond lodgements
├── audit.py                 # cross-source output summary / integrity check
└── diagnostics.py           # ad-hoc comparison/analysis helpers
tests/                       # contract + per-source regression tests
scripts/                     # rclone Drive sync + update-and-push helpers
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
data/manifests/nswgov_sales_manifest.csv
data/manifests/rentboard_lodgements_manifest.csv
```

Manifest columns: `source, dataset, period_start, period_end, path, rows, sha256, created_at_utc`.

Legacy monolith CSVs (`data/nswgov_df.csv`, `data/rentboard_df.csv`) are optional
compatibility exports only, produced on demand by `export-legacy`.

The data dir is resolved by `paths.resolve_data_dir`: explicit `--data-dir` >
`PROPERTYIQ_DATA_DIR` > `DATA_DIR` > repo-local `data/`.

## The sources

**nswgov** — NSW Valuer General property sales.
Source: https://valuation.property.nsw.gov.au/embed/propertySalesInformation
`.DAT` file format spec: https://www.valuergeneral.nsw.gov.au/__data/assets/pdf_file/0015/216402/Current_Property_Sales_Data_File_Format_2001_to_Current.pdf
Explicit stages, all incremental/idempotent:

| Stage | Function | In → Out |
|-------|----------|----------|
| pull | `pull_nswgov` | Scrapes `yearly` (`YYYY.zip`) and `weekly` (`YYYYMMDD.zip`) links, downloads & unzips new periods into `data/raw/nswgov/...`. |
| extract | `extract_nswgov` | Parses `;`-delimited `.DAT` (record types A/B/C/D via `nswgov_dat_map`), melts to long form, writes one CSV per period to `data/interim/nswgov/output_etl2/`. |
| transform | `transform_nswgov` | Keeps record_type `B`, pivots labels to `FINAL_COLUMNS`, writes `normalized/nswgov/sales/period=YYYYMMDD.csv` (atomic temp-then-replace) and refreshes the manifest. |

**rentboard** — NSW rental bond lodgements. Self-contained `update_rentboard`:
scrapes `.xlsx` links, classifies annual vs monthly by title regex, prefers
monthly when a year has months, normalizes to `FINAL_COLUMNS`, and writes/merges
`normalized/rentboard/lodgements/year=YYYY/month=MM.csv` + manifest.
Source: https://www.nsw.gov.au/housing-and-construction/rental-forms-surveys-and-data/rental-bond-data

## Running

Managed with **uv**. `uv sync` builds the env (Python from `.python-version`,
package installed editable, dev tools included); `uv run` executes in it. The CLI
is the `propertyiq-getdata` console script (or `python -m propertyiq_getdata`).

```bash
uv sync
uv run propertyiq-getdata nswgov update --data-dir data
uv run propertyiq-getdata rentboard update --data-dir data
uv run propertyiq-getdata audit --data-dir data
uv run pytest
```

Migration/compat: `nswgov|rentboard migrate-legacy` splits an old monolith CSV
into partitions; `export-legacy` stacks partitions back into the monolith shape;
`nswgov manifest` / `rentboard manifest` rebuild a manifest from partitions.

Dependencies are declared in `pyproject.toml` and pinned in `uv.lock` (commit
both). Runtime: `beautifulsoup4, pandas, numpy, requests, openpyxl` (+
`matplotlib` for `diagnostics.py`); dev group: `pytest`. Add one with
`uv add <pkg>` (or `uv add --dev <pkg>`). Note: the old `stem`/Tor dependency was
only used by `archive/` and is no longer installed.

## Conventions & gotchas

- Every stage is **incremental/idempotent** — it detects already-processed
  periods (via the manifest, then partitions, then a legacy CSV) and skips them.
  The "latest period" logic lives in `latest_final_period` (nswgov) and
  `latest_lodgement_dt` (rentboard).
- Stages **raise on zero rows** (`ZERO rows added ... investigate`) — that is the
  signal the source layout changed and a scraper needs updating.
- **Site-layout changes are the usual break point.** nswgov depends on `.zip`
  href patterns and `yearly`/`weekly` classification in `discover_links`;
  rentboard depends on link title regexes (`MONTH_PATTERN`, the year regex) and
  the xlsx header row (`read_excel(header=2)`) + expected `XLSX_COLUMNS`. Update
  these when a scrape returns nothing.
- Partition writes are **atomic** (write `.csv.tmp`, then `Path.replace`), so an
  interrupted run never leaves a half-written partition.
- After changing output shape, update the tests in `tests/` — they pin the
  partition naming, schemas, and manifest columns.

## Reviving a historical source

See [`archive/README.md`](./archive/README.md). Copy the `nswgov`/`rentboard`
module shape into a new `propertyiq_getdata/<source>.py`; do not port the old
`/Users/macmac/...` paths, `from config import *`, or Tor plumbing.
