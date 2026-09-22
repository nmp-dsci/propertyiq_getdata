"""Land the manifests in the central Postgres and build ``staging`` with dbt.

Ownership rule (plan s03, decision D7): this package owns ``raw`` (verbatim
landing of every manifest partition) and ``staging`` (typed, cleaned,
record-grain tables that any app on the platform imports over
``postgres_fdw``). Marts are app-shaped and live with the app that needs them
-- there are none here.

Layout mirrors the rest of the package: ``registry`` says *what* is loaded,
``load`` is the mechanics, ``schema`` is the one-off DDL, ``dbt`` wraps the
dbt CLI, ``pipeline`` is the ``db update`` orchestration the CLI calls.
"""

from .connection import connect, database_url
from .pipeline import export_fixture, init_db, run_dbt_stage, smoke, update_db
from .registry import LOAD_SPECS, LoadSpec, raw_table_for

__all__ = [
    "LOAD_SPECS",
    "LoadSpec",
    "connect",
    "database_url",
    "export_fixture",
    "init_db",
    "raw_table_for",
    "run_dbt_stage",
    "smoke",
    "update_db",
]
