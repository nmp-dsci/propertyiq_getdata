# CLAUDE.md — propertyiq_getdata

See **[AGENTS.md](./AGENTS.md)** for the full guide to this repo.

**TL;DR:** Python ETL that scrapes NSW property data. It is one package,
`propertyiq_getdata/`, organized by responsibility: sources live in `sources/`
(`nswgov.py`, `rentboard.py`), shared mechanics in `core/`, driven by a CLI
(`python -m propertyiq_getdata`). Only `nswgov` and `rentboard` are actively
maintained; historical code lives in `archive/`. Read AGENTS.md before making
changes.
