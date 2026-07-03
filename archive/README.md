# archive/ — historical, unmaintained code

This directory holds the pre-refactor code that is **not** part of the active
`nswgov` / `rentboard` collection pipeline. None of it is imported, run, or tested
by the current project. It is kept as **reference context** so a source could be
revived later without archaeology through git history.

> Nothing here runs as-is. Every file assumes the original author's machine
> (`/Users/macmac/...`), a Tor proxy, or datasets that no longer exist. Treat it
> as documentation of *how a source used to be scraped*, not as runnable code.

## What lives here

| Path | What it was | State |
|------|-------------|-------|
| `etl1_pull/REA.py`, `domain.py`, `auhouse_rent.py`, `*-auction.py` | Scrapers for realestate.com.au, Domain, and Australian house-price/auction sites. | Python 3, but hardcode `sys.path.append('/Users/macmac/.../propertyiq_getdata')`, `from config import *`, `from utils import *`. REA needs `fake_useragent`; several route through Tor via `utils/`. |
| `etl2_extract/*.py`, `etl3_transform/*.py` | Per-source extract/transform stages that mirrored the old nswgov pipeline shape. | Same import/path assumptions as above. |
| `etl4_load/s1..s4_*.py` | The old "propertyIQ" master build: joined all sources into a property/sold-price universe. | Hardcodes `/Users/macmac/Documents/Property/...` in/out dirs. This joining/serving work now belongs in the **downstream database project**, not here. |
| `utils/` | Shared scraping helpers: href parsing, Tor session rotation (`stem`), HTML pull/extract. | Imported by the legacy scrapers via `from utils import *`. |
| `config.py` | Env-var config (`OUTPUT_DIR`, `DATEID`) plus a Flask `Config` class. | Mostly commented out; documents which env vars the legacy code expected. |
| `website/` | An unfinished Flask scaffold for a results dashboard. | Placeholder only — `README.md` literally says "insert intuitive guide". Never built out. |
| `investigations/` | One-off analysis scripts (postcode views, inner-west, apartments, station pricing). | Some are Python 2 (`#!/usr/bin/env python2`). Scratch analysis, not pipeline. |
| `run_20190202.sh`, `run_20240120.sh` | The original run recipes — the manual order the author ran scrapers and the master build in. | Point at absolute paths on the author's machine. Useful as a record of the old end-to-end order. |

## Why it was archived

The repo was refactored to be **collection-only** for the two sources that are
still maintained. See the top-level `README.md` and `AGENTS.md`. The active
pipeline is the `propertyiq_getdata/` package; `nswgov` and `rentboard` are the
only living sources.

## Reviving a source

The active `nswgov` and `rentboard` code in `propertyiq_getdata/` is the template
to copy. To bring back, say, Domain:

1. Read `archive/etl1_pull/domain.py` for the source URL, the link-discovery
   logic, and the parsing quirks — that is the reusable knowledge.
2. Add a `propertyiq_getdata/domain.py` modelled on `nswgov.py` /
   `rentboard.py`: a `SOURCE_ID`, `SOURCE_URL`, `FINAL_COLUMNS`, link discovery,
   normalized period partitions under `data/normalized/domain/...`, and a
   manifest via `manifest.write_manifest`.
3. Wire `pull` / `update` subcommands into `propertyiq_getdata/cli.py` and add
   tests under `tests/`.
4. **Do not** port the `/Users/macmac/...` paths, `from config import *`,
   `from utils import *`, or the Tor rotation unless you re-establish a real need
   — resolve data locations through `propertyiq_getdata/paths.py` instead.

Before investing, confirm the source site still exists and its layout still
matches what the archived scraper expects; these break most often on site
redesigns.
