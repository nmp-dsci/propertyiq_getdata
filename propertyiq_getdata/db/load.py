"""Manifest-driven ``COPY`` of normalized CSV partitions into ``raw`` (decision D2).

The manifest already says, per partition, where the file is, how many rows
it has and its sha256. ``meta.load_state`` says the same for what is in the
table. The diff between the two is the work:

* sha256 differs or the partition is unknown  -> ``replace`` (delete + COPY)
* partition in state but gone from manifest   -> ``delete`` (partition mode only)
* everything else                              -> ``skip``

Raw tables are created lazily from the CSV header, every column ``text``,
plus ``_partition``, ``_sha256``, ``_loaded_at``. Blank cells land as ``''``,
never NULL (the pandas writer's convention), so staging SQL keeps the
``coalesce(x, '') <> ''`` idiom the cleaning rules were written with. A later file whose header
differs from the table is an error, not an ``ALTER`` -- the source contract
changed and someone should look. Each partition is one transaction; the row
count is asserted against the manifest before commit.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pandas as pd

from .registry import LoadMode, LoadSpec

LOADER_COLUMNS = ("_partition", "_sha256", "_loaded_at")
Action = Literal["replace", "delete", "skip"]

_IDENT = re.compile(r"^[a-z_][a-z0-9_]*$")


@dataclass(frozen=True)
class LoadAction:
    action: Action
    partition: str
    path: str  # manifest-relative, "" for delete
    sha256: str
    rows: int


# --------------------------------------------------------------------------- pure


def partition_of(path: str, source: str, dataset: str) -> str:
    """The partition key is the manifest path inside the dataset directory, minus ``.csv``.

    ``normalized/nswgov/sales/period=20120102.csv`` -> ``period=20120102``;
    ``normalized/rentboard/lodgements/year=2016/month=01.csv`` -> ``year=2016/month=01``;
    ``normalized/abs_ts/cpi/asof=2026-09-21.csv`` -> ``asof=2026-09-21``.
    """

    prefix = f"normalized/{source}/{dataset}/"
    value = str(path).replace("\\", "/")
    if not value.startswith(prefix) or not value.endswith(".csv"):
        raise ValueError(f"manifest path {path!r} is not under {prefix}*.csv")
    return value[len(prefix) : -len(".csv")]


def plan_actions(
    manifest: pd.DataFrame,
    state: dict[str, tuple[str, int]],
    *,
    mode: LoadMode,
    full_refresh: bool = False,
) -> list[LoadAction]:
    """Diff manifest rows (this dataset only) against ``{partition: (sha256, rows)}``.

    Pure, so the incremental logic is testable without a database. Order is
    deterministic: replaces by partition, then deletes by partition.
    """

    replaces: list[LoadAction] = []
    seen: set[str] = set()
    for row in manifest.itertuples(index=False):
        partition = partition_of(row.path, row.source, row.dataset)
        if partition in seen:
            raise ValueError(f"manifest lists partition {partition!r} twice")
        seen.add(partition)
        current = None if full_refresh else state.get(partition)
        rows = int(row.rows)
        if current is not None and current[0] == row.sha256 and current[1] == rows:
            replaces.append(LoadAction("skip", partition, row.path, row.sha256, rows))
        else:
            replaces.append(LoadAction("replace", partition, row.path, row.sha256, rows))
    deletes: list[LoadAction] = []
    if mode == "partition":
        for partition, (sha, rows) in sorted(state.items()):
            if partition not in seen:
                deletes.append(LoadAction("delete", partition, "", sha, rows))
    return sorted(replaces, key=lambda a: a.partition) + deletes


def read_header(path: Path) -> list[str]:
    with path.open(newline="", encoding="utf-8") as handle:
        return next(csv.reader(handle))


def check_columns(header: list[str]) -> list[str]:
    """CSV header -> raw column names: lower-cased (``dim_REGION`` -> ``dim_region``), validated.

    Postgres folds unquoted identifiers anyway; lower-casing here keeps the
    contract explicit and makes ``dim_*`` columns consistent across datasets.
    Rejects anything that is not a plain identifier, duplicates after folding,
    and clashes with the loader's own columns.
    """

    columns = [c.strip().lower() for c in header]
    bad = [c for c in columns if not _IDENT.fullmatch(c)]
    if bad:
        raise ValueError(f"CSV header has columns that are not plain snake_case identifiers: {bad}")
    clash = [c for c in columns if c in LOADER_COLUMNS]
    if clash:
        raise ValueError(f"CSV header collides with loader columns: {clash}")
    if len(set(columns)) != len(columns):
        raise ValueError("CSV header has duplicate columns (after lower-casing)")
    return columns


def header_matches(existing: list[str], header: list[str]) -> bool:
    """True when the table's data columns (loader columns excluded) equal the CSV header, in order."""

    data_columns = [c for c in existing if c not in LOADER_COLUMNS]
    return data_columns == list(header)


# --------------------------------------------------------------------------- database


def _sql():
    from psycopg import sql

    return sql


def table_columns(conn, table: str) -> list[str] | None:
    with conn.cursor() as cur:
        cur.execute(
            "select column_name from information_schema.columns "
            "where table_schema = 'raw' and table_name = %s order by ordinal_position",
            (table,),
        )
        rows = cur.fetchall()
    return [r[0] for r in rows] or None


def ensure_raw_table(conn, table: str, header: list[str]) -> None:
    """Create ``raw.<table>`` from the header, or verify the existing table matches it."""

    sql = _sql()
    existing = table_columns(conn, table)
    if existing is not None:
        if not header_matches(existing, header):
            raise RuntimeError(
                f"raw.{table} columns {[c for c in existing if c not in LOADER_COLUMNS]} "
                f"do not match the CSV header {header}; the source contract changed. "
                f"Migrate the table, then `db load --full-refresh --dataset ...`."
            )
        return
    columns = [sql.SQL("{} text").format(sql.Identifier(c)) for c in header]
    columns += [
        sql.SQL("_partition text not null"),
        sql.SQL("_sha256 text not null"),
        sql.SQL("_loaded_at timestamptz not null default now()"),
    ]
    with conn.transaction(), conn.cursor() as cur:
        cur.execute(sql.SQL("create table raw.{} ({})").format(sql.Identifier(table), sql.SQL(", ").join(columns)))
        cur.execute(
            sql.SQL("create index {} on raw.{} (_partition)").format(
                sql.Identifier(f"{table}__partition_idx"), sql.Identifier(table)
            )
        )


def load_state(conn, table: str) -> dict[str, tuple[str, int]]:
    with conn.cursor() as cur:
        cur.execute(
            "select partition, sha256, rows from meta.load_state where table_name = %s",
            (table,),
        )
        return {p: (s, int(r)) for p, s, r in cur.fetchall()}


def delete_partition(conn, table: str, partition: str) -> int:
    sql = _sql()
    with conn.transaction(), conn.cursor() as cur:
        cur.execute(
            sql.SQL("delete from raw.{} where _partition = %s").format(sql.Identifier(table)),
            (partition,),
        )
        deleted = cur.rowcount
        cur.execute(
            "delete from meta.load_state where table_name = %s and partition = %s",
            (table, partition),
        )
    return deleted


def truncate_table(conn, table: str) -> None:
    sql = _sql()
    with conn.transaction(), conn.cursor() as cur:
        cur.execute(sql.SQL("truncate raw.{}").format(sql.Identifier(table)))
        cur.execute("delete from meta.load_state where table_name = %s", (table,))


def load_dataset(
    conn,
    spec: LoadSpec,
    *,
    data_dir: Path,
    manifest: pd.DataFrame,
    full_refresh: bool = False,
    dry_run: bool = False,
    log=print,
) -> pd.DataFrame:
    """Apply the plan for one dataset. Returns one row per action with its status."""

    subset = manifest[(manifest["source"] == spec.source) & (manifest["dataset"] == spec.dataset)]
    if subset.empty:
        raise RuntimeError(f"manifest has no rows for {spec.key}; run the source's `update`/`manifest` stage first")

    exists = table_columns(conn, spec.table) is not None
    state = {} if (full_refresh or not exists) else load_state(conn, spec.table)
    actions = plan_actions(subset, state, mode=spec.mode, full_refresh=full_refresh)
    report = []
    header: list[str] | None = None
    if full_refresh and exists and not dry_run:
        truncate_table(conn, spec.table)
    for action in actions:
        row = {
            "table": spec.table,
            "partition": action.partition,
            "action": action.action,
            "rows": action.rows,
        }
        if dry_run or action.action == "skip":
            row["status"] = "planned" if dry_run else "skipped"
            report.append(row)
            continue
        if action.action == "delete":
            row["rows"] = delete_partition(conn, spec.table, action.partition)
            row["status"] = "deleted"
            report.append(row)
            continue
        path = data_dir / action.path
        if header is None:
            header = check_columns(read_header(path))
            ensure_raw_table(conn, spec.table, header)
        elif check_columns(read_header(path)) != header:
            raise RuntimeError(f"{path} header differs from the first file of {spec.key}")
        row["rows"] = copy_partition(conn, spec.table, header, path, action)
        row["status"] = "loaded"
        log(f"  raw.{spec.table} {action.partition}: {row['rows']} rows")
        report.append(row)
    return pd.DataFrame(report, columns=["table", "partition", "action", "rows", "status"])


def copy_partition(conn, table: str, header: list[str], path: Path, action: LoadAction) -> int:
    """DELETE the partition, COPY the file, stamp, verify the count, record state -- one transaction.

    COPY goes through a temp table so ``_partition``/``_sha256`` are stamped in the same statement.

    so ``_partition``/``_sha256`` are stamped in the same statement: ``COPY``
    cannot supply constants for columns the file lacks, and the target's
    ``_partition`` is ``NOT NULL``.
    """

    sql = _sql()
    ident = sql.Identifier(table)
    cols = sql.SQL(", ").join(sql.Identifier(c) for c in header)
    with conn.transaction(), conn.cursor() as cur:
        cur.execute(
            sql.SQL("delete from raw.{} where _partition = %s").format(ident),
            (action.partition,),
        )
        cur.execute(
            sql.SQL("create temp table _incoming (like raw.{} including defaults) on commit drop").format(ident)
        )
        cur.execute("alter table _incoming drop column _partition, drop column _sha256, drop column _loaded_at")
        # NULL sentinel that never occurs in the data: a blank CSV cell must land
        # as '' (what pandas wrote), not NULL, so staging SQL can keep the
        # `coalesce(x, '') <> ''` idiom the cleaning rules were written with.
        copy_sql = sql.SQL("copy _incoming ({}) from stdin (format csv, header true, null '\\N')").format(cols)
        with path.open("rb") as handle, cur.copy(copy_sql) as copy:
            while chunk := handle.read(1 << 20):
                copy.write(chunk)
        cur.execute(
            sql.SQL("insert into raw.{} ({}, _partition, _sha256) select {}, %s, %s from _incoming").format(
                ident, cols, cols
            ),
            (action.partition, action.sha256),
        )
        loaded = cur.rowcount
        if loaded != action.rows:
            raise RuntimeError(
                f"raw.{table} partition {action.partition}: loaded {loaded} rows, manifest says {action.rows}"
            )
        cur.execute(
            "insert into meta.load_state (table_name, partition, sha256, rows, path, loaded_at) "
            "values (%s, %s, %s, %s, %s, now()) "
            "on conflict (table_name, partition) do update set "
            "sha256 = excluded.sha256, rows = excluded.rows, path = excluded.path, loaded_at = now()",
            (table, action.partition, action.sha256, loaded, action.path),
        )
    return loaded


__all__ = [
    "LOADER_COLUMNS",
    "LoadAction",
    "check_columns",
    "copy_partition",
    "ensure_raw_table",
    "header_matches",
    "load_dataset",
    "load_state",
    "partition_of",
    "plan_actions",
    "read_header",
    "table_columns",
]
