"""One-off DDL for the ``propertyiq`` database: schemas, ``meta`` tables, grants.

Run as the superuser (``db init``, platform D16). Idempotent. The database
itself and the two roles are created by ``make -C nmp-central-ai db-init``
from the registry; this is everything *inside* the database that dbt and the
loader assume exists.

Ownership: ``propertyiq_owner`` owns every schema so dbt can create tables in
them. ``propertyiq_ro`` can read ``staging`` and ``meta`` -- that is the
consumer contract -- but not ``raw``, which is verbatim landing and not a
published interface.
"""

from __future__ import annotations

OWNER = "propertyiq_owner"
READER = "propertyiq_ro"
DATABASE = "propertyiq"

SCHEMAS = ("raw", "staging", "meta")
READABLE_SCHEMAS = ("staging", "meta")

INIT_SQL = f"""
grant connect on database {DATABASE} to {OWNER}, {READER};

create schema if not exists raw authorization {OWNER};
create schema if not exists staging authorization {OWNER};
create schema if not exists meta authorization {OWNER};

-- What is loaded, from which file, at which content hash. One row per
-- (table, partition); the loader's incremental signal.
create table if not exists meta.load_state (
    table_name  text        not null,
    partition   text        not null,
    sha256      text        not null,
    rows        bigint      not null,
    path        text        not null,
    loaded_at   timestamptz not null default now(),
    primary key (table_name, partition)
);
alter table meta.load_state owner to {OWNER};

-- One row per `db update` (or `db load` / `db dbt` run on its own).
create table if not exists meta.pipeline_runs (
    id            bigserial   primary key,
    started_at    timestamptz not null,
    finished_at   timestamptz,
    stage         text        not null,   -- load | dbt | update
    status        text        not null,   -- running | success | failed
    datasets      int,
    rows_loaded   bigint,
    dbt_pass      int,
    dbt_total     int,
    git_sha       text,
    detail        jsonb       not null default '{{}}'::jsonb
);
alter table meta.pipeline_runs owner to {OWNER};
alter sequence meta.pipeline_runs_id_seq owner to {OWNER};

grant usage on schema staging, meta to {READER};
grant select on all tables in schema staging, meta to {READER};
-- Tables dbt creates later inherit the grant.
alter default privileges for role {OWNER} in schema staging grant select on tables to {READER};
alter default privileges for role {OWNER} in schema meta grant select on tables to {READER};
"""


def init_schema(conn) -> None:
    """Apply :data:`INIT_SQL` in one transaction."""

    with conn.transaction(), conn.cursor() as cur:
        cur.execute(INIT_SQL)


__all__ = [
    "DATABASE",
    "INIT_SQL",
    "OWNER",
    "READABLE_SCHEMAS",
    "READER",
    "SCHEMAS",
    "init_schema",
]
