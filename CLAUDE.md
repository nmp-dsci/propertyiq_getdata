# CLAUDE.md — propertyiq_getdata

See **[AGENTS.md](./AGENTS.md)** for the full guide to this repo.

**TL;DR:** Python ETL that scrapes NSW property data and ABS/RBA economic
series and lands them in the central Postgres. It is one package,
`propertyiq_getdata/`, organized by responsibility: sources live in `sources/`
(`nswgov.py`, `rentboard.py`, `abs_ts.py`, `rba.py`), shared mechanics in
`core/`, the Postgres loader in `db/` (dbt project in `dbt/`), driven by a CLI
(`python -m propertyiq_getdata`). This repo owns `raw` + `staging`; apps own
their marts. Historical code lives in `archive/`. Read AGENTS.md before making
changes.
