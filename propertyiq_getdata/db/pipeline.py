"""The ``db`` CLI stages: ``init``, ``load``, ``dbt``, ``update``, ``smoke``, ``export-fixture``."""

from __future__ import annotations

import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from ..core.paths import PipelinePaths, resolve_data_dir
from .connection import connect
from .dbt import DBT_DIR, run_dbt, test_counts
from .load import load_dataset
from .registry import LOAD_SPECS, LoadSpec, select_specs
from .schema import init_schema

DBT_STAGES: dict[str, list[list[str]]] = {
    "seed": [["seed"]],
    "build": [["build"]],
    "docs": [["docs", "generate", "--no-compile"]],
    "all": [["seed"], ["build"], ["docs", "generate", "--no-compile"]],
}


def _git_sha() -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=DBT_DIR.parent,
        ).stdout.strip()
    except Exception:  # noqa: BLE001 -- telemetry only
        return None


class RunRecord:
    """One ``meta.pipeline_runs`` row, opened at start and closed at the end."""

    def __init__(self, conn, stage: str):
        self.conn = conn
        self.started = time.time()
        with conn.transaction(), conn.cursor() as cur:
            cur.execute(
                "insert into meta.pipeline_runs (started_at, stage, status, git_sha) values (now(), %s, 'running', %s) "
                "returning id",
                (stage, _git_sha()),
            )
            self.id = cur.fetchone()[0]

    def close(self, status: str, **fields) -> None:
        detail = {k: v for k, v in fields.items() if k not in {"datasets", "rows_loaded", "dbt_pass", "dbt_total"}}
        with self.conn.transaction(), self.conn.cursor() as cur:
            cur.execute(
                "update meta.pipeline_runs set finished_at = now(), status = %s, datasets = %s, rows_loaded = %s, "
                "dbt_pass = %s, dbt_total = %s, detail = %s::jsonb where id = %s",
                (
                    status,
                    fields.get("datasets"),
                    fields.get("rows_loaded"),
                    fields.get("dbt_pass"),
                    fields.get("dbt_total"),
                    json.dumps({**detail, "duration_s": round(time.time() - self.started, 1)}),
                    self.id,
                ),
            )


# --------------------------------------------------------------------------- stages


class _keep:
    """Context manager that yields an existing connection without closing it."""

    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self.conn

    def __exit__(self, *exc):
        return False


def init_db(*, log=print) -> None:
    """Schemas, ``meta`` tables and grants, as the superuser. Idempotent."""

    with connect("admin") as conn:
        init_schema(conn)
    log("==> propertyiq: schemas raw/staging/meta, meta.load_state, meta.pipeline_runs, grants -- ok")


def _manifests(paths: PipelinePaths, specs: list[LoadSpec]) -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    for name in sorted({s.manifest for s in specs}):
        path = getattr(paths, name)
        if not path.exists():
            raise RuntimeError(f"manifest {path} is missing; run the source's `update` stage first")
        out[name] = pd.read_csv(path, dtype=str)
    return out


def load_db(
    *,
    data_dir: str | Path | None = None,
    datasets: list[str] | None = None,
    full_refresh: bool = False,
    dry_run: bool = False,
    record: bool = True,
    conn=None,
    log=print,
) -> pd.DataFrame:
    """``db load``: every selected dataset's manifest -> ``raw``. Returns one row per partition action."""

    paths = PipelinePaths(resolve_data_dir(data_dir))
    specs = select_specs(datasets)
    manifests = _manifests(paths, specs)
    reports: list[pd.DataFrame] = []
    with connect("owner") if conn is None else _keep(conn) as conn:
        run = RunRecord(conn, "load") if (record and not dry_run) else None
        try:
            for spec in specs:
                log(f"==> raw.{spec.table} ({spec.mode}, {spec.key})")
                reports.append(
                    load_dataset(
                        conn,
                        spec,
                        data_dir=paths.data_dir,
                        manifest=manifests[spec.manifest],
                        full_refresh=full_refresh,
                        dry_run=dry_run,
                        log=log,
                    )
                )
        except Exception as exc:
            if run:
                run.close("failed", error=str(exc)[:500])
            raise
        report = pd.concat(reports, ignore_index=True)
        if run:
            loaded = report[report["status"] == "loaded"]
            run.close("success", datasets=len(specs), rows_loaded=int(loaded["rows"].sum()))
    return report


def run_dbt_stage(stage: str = "all", *, record: bool = True, conn=None, log=print) -> tuple[int | None, int | None]:
    """``db dbt [seed|build|docs|all]``. Raises on a non-zero dbt exit."""

    commands = DBT_STAGES[stage]
    with connect("owner") if conn is None else _keep(conn) as conn:
        run = RunRecord(conn, "dbt") if record else None
        for args in commands:
            code = run_dbt(args, log=log)
            if code != 0:
                passed, total = test_counts()
                if run:
                    run.close(
                        "failed",
                        dbt_pass=passed,
                        dbt_total=total,
                        command=" ".join(args),
                    )
                raise RuntimeError(f"dbt {' '.join(args)} exited {code}")
        passed, total = test_counts()
        if run:
            run.close("success", dbt_pass=passed, dbt_total=total)
    return passed, total


def update_db(
    *,
    data_dir: str | Path | None = None,
    datasets: list[str] | None = None,
    full_refresh: bool = False,
    dry_run: bool = False,
    log=print,
) -> pd.DataFrame:
    """``db update`` = load (all datasets) -> dbt seed + build + docs, recorded as one run."""

    with connect("owner") as conn:
        run = None if dry_run else RunRecord(conn, "update")
        try:
            report = load_db(
                data_dir=data_dir,
                datasets=datasets,
                full_refresh=full_refresh,
                dry_run=dry_run,
                record=False,
                conn=conn,
                log=log,
            )
            if dry_run:
                return report
            passed, total = run_dbt_stage("all", record=False, conn=conn, log=log)
        except Exception as exc:
            if run:
                run.close("failed", error=str(exc)[:500])
            raise
        loaded = report[report["status"] == "loaded"]
        run.close(
            "success",
            datasets=len(select_specs(datasets)),
            rows_loaded=int(loaded["rows"].sum()),
            dbt_pass=passed,
            dbt_total=total,
        )
    log(f"==> db update complete: {len(loaded)} partitions loaded, dbt tests {passed}/{total}")
    return report


SMOKE_SQL = (
    "select (select count(*) from staging.econ_series where period_start >= current_date - interval '1 year'), "
    "(select count(*) from staging.property_sales where sale_date >= current_date - interval '1 year'), "
    "(select max(loaded_at) from meta.load_state)"
)


def smoke(*, log=print) -> bool:
    """Zero-LLM proof for ``make check``: recent rows exist in staging, as the read-only role."""

    with connect("ro") as conn, conn.cursor() as cur:
        cur.execute(SMOKE_SQL)
        econ, sales, loaded_at = cur.fetchone()
    ok = econ > 0 and sales > 0 and loaded_at is not None
    log(f"smoke: econ_series(1y)={econ} property_sales(1y)={sales} last_load={loaded_at} -> {'ok' if ok else 'FAIL'}")
    return ok


FIXTURE_TABLES = (
    "property_sales",
    "property_rent",
    "geo_postcode",
    "econ_series",
    "econ_headline_series",
)


def export_fixture(out: str | Path, *, limit: int = 500, log=print) -> Path:
    """A small SQL fixture of ``staging`` for consumers' CI (plan §07): DDL + COPY blocks.

    Rows are the newest ``limit`` per table so a consumer's freshness tests
    still pass against the fixture.
    """

    from psycopg import sql

    order = {
        "property_sales": "sale_date desc",
        "property_rent": "rent_date desc",
        "econ_series": "period_start desc",
    }
    out = Path(out)
    lines = [
        f"-- propertyiq staging fixture, exported {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        "-- Load into an empty database: psql -v ON_ERROR_STOP=1 -f <this file>",
        "create schema if not exists staging;",
    ]
    with connect("ro") as conn, conn.cursor() as cur:
        for table in FIXTURE_TABLES:
            cur.execute(
                "select column_name, data_type from information_schema.columns "
                "where table_schema = 'staging' and table_name = %s order by ordinal_position",
                (table,),
            )
            cols = cur.fetchall()
            if not cols:
                raise RuntimeError(f"staging.{table} does not exist; run `db update` first")
            lines.append(f"drop table if exists staging.{table};")
            lines.append(f"create table staging.{table} (" + ", ".join(f'"{c}" {t}' for c, t in cols) + ");")
            query = sql.SQL("select * from staging.{}").format(sql.Identifier(table))
            if table in order:
                query = query + sql.SQL(f" order by {order[table]} limit {int(limit)}")
            lines.append(f"copy staging.{table} from stdin;")
            with cur.copy(sql.SQL("copy ({}) to stdout").format(query)) as copy:
                data = b"".join(copy)
            lines.append(data.decode("utf-8").rstrip("\n"))
            lines.append("\\.")
            n_rows = data.count(b"\n")
            log(f"  staging.{table}: {n_rows} rows")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n")
    return out


__all__ = [
    "DBT_STAGES",
    "FIXTURE_TABLES",
    "LOAD_SPECS",
    "RunRecord",
    "export_fixture",
    "init_db",
    "load_db",
    "run_dbt_stage",
    "smoke",
    "update_db",
]
