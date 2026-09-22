"""db loader: partition keys, incremental plan, header checks, registry, dbt env. Offline.

The COPY path itself is exercised by the ``live`` test at the bottom against
the central Postgres (deselected by default; ``uv run --env-file .env pytest -m live``).
"""

from __future__ import annotations

import json
import os

import pandas as pd
import pytest

from propertyiq_getdata.db.connection import ENV_VARS, DatabaseUnavailable, database_url
from propertyiq_getdata.db.dbt import dbt_env, test_counts
from propertyiq_getdata.db.load import (
    LOADER_COLUMNS,
    LoadAction,
    check_columns,
    header_matches,
    partition_of,
    plan_actions,
)
from propertyiq_getdata.db.registry import (
    LOAD_KEYS,
    LOAD_SPECS,
    LoadSpec,
    raw_table_for,
    select_specs,
)


def _manifest(rows):
    return pd.DataFrame(rows, columns=["source", "dataset", "path", "rows", "sha256"])


# ----------------------------------------------------------------- partition keys / registry


def test_partition_key_is_manifest_path_inside_dataset_dir():
    assert partition_of("normalized/nswgov/sales/period=20120102.csv", "nswgov", "sales") == "period=20120102"
    assert (
        partition_of(
            "normalized/rentboard/lodgements/year=2016/month=01.csv",
            "rentboard",
            "lodgements",
        )
        == "year=2016/month=01"
    )
    assert partition_of("normalized/abs_ts/cpi/asof=2026-09-21.csv", "abs_ts", "cpi") == "asof=2026-09-21"
    with pytest.raises(ValueError, match="not under"):
        partition_of("normalized/abs_ts/wpi/asof=2026-09-21.csv", "abs_ts", "cpi")


def test_registry_covers_every_source_with_the_naming_rule():
    tables = {spec.table for spec in LOAD_SPECS}
    assert {
        "nswgov_sales",
        "rentboard_lodgements",
        "abs_ts_cpi",
        "rba_cash_rate",
    } <= tables
    assert len(tables) == 13
    assert raw_table_for("rba", "rba_cash_rate") == "rba_cash_rate"  # no double prefix
    assert raw_table_for("abs_ts", "cpi") == "abs_ts_cpi"
    assert all(spec.mode == "snapshot" for spec in LOAD_SPECS if spec.source in {"abs_ts", "rba"})
    assert all(spec.mode == "partition" for spec in LOAD_SPECS if spec.source in {"nswgov", "rentboard"})


def test_select_specs_accepts_source_or_source_slash_dataset():
    assert [s.key for s in select_specs(None)] == list(LOAD_KEYS)
    assert [s.key for s in select_specs(["rba"])] == [
        "rba/rba_cash_rate",
        "rba/rba_lending_rates",
        "rba/rba_rate_changes",
    ]
    assert [s.key for s in select_specs(["abs_ts/cpi", "abs_ts"])][0] == "abs_ts/cpi"
    assert len(select_specs(["abs_ts/cpi", "abs_ts"])) == 8  # no duplicates
    with pytest.raises(ValueError, match="Unknown dataset"):
        select_specs(["census"])


# ----------------------------------------------------------------- incremental plan


def test_plan_replaces_new_and_changed_partitions_and_skips_unchanged():
    manifest = _manifest(
        [
            (
                "nswgov",
                "sales",
                "normalized/nswgov/sales/period=20260907.csv",
                "10",
                "aaa",
            ),
            (
                "nswgov",
                "sales",
                "normalized/nswgov/sales/period=20260914.csv",
                "12",
                "bbb",
            ),
            (
                "nswgov",
                "sales",
                "normalized/nswgov/sales/period=20260921.csv",
                "9",
                "ccc",
            ),
        ]
    )
    state = {"period=20260907": ("aaa", 10), "period=20260914": ("old", 12)}
    plan = plan_actions(manifest, state, mode="partition")
    assert [(a.action, a.partition) for a in plan] == [
        ("skip", "period=20260907"),
        ("replace", "period=20260914"),
        ("replace", "period=20260921"),
    ]
    assert plan[2] == LoadAction(
        "replace",
        "period=20260921",
        "normalized/nswgov/sales/period=20260921.csv",
        "ccc",
        9,
    )


def test_plan_replaces_when_row_count_changed_even_if_sha_matches():
    manifest = _manifest(
        [
            (
                "nswgov",
                "sales",
                "normalized/nswgov/sales/period=20260907.csv",
                "11",
                "aaa",
            )
        ]
    )
    plan = plan_actions(manifest, {"period=20260907": ("aaa", 10)}, mode="partition")
    assert plan[0].action == "replace"


def test_plan_deletes_vanished_partitions_only_in_partition_mode():
    manifest = _manifest([("abs_ts", "cpi", "normalized/abs_ts/cpi/asof=2026-09-21.csv", "5", "aaa")])
    state = {"asof=2026-09-21": ("aaa", 5), "asof=2026-08-01": ("zzz", 5)}
    snapshot_plan = plan_actions(manifest, state, mode="snapshot")
    assert [(a.action, a.partition) for a in snapshot_plan] == [("skip", "asof=2026-09-21")]  # vintages kept

    manifest = _manifest([("nswgov", "sales", "normalized/nswgov/sales/period=20260907.csv", "5", "aaa")])
    state = {"period=20260907": ("aaa", 5), "period=20260831": ("zzz", 5)}
    partition_plan = plan_actions(manifest, state, mode="partition")
    assert [(a.action, a.partition) for a in partition_plan] == [
        ("skip", "period=20260907"),
        ("delete", "period=20260831"),
    ]


def test_plan_full_refresh_ignores_state():
    manifest = _manifest([("nswgov", "sales", "normalized/nswgov/sales/period=20260907.csv", "5", "aaa")])
    plan = plan_actions(manifest, {"period=20260907": ("aaa", 5)}, mode="partition", full_refresh=True)
    assert plan[0].action == "replace"


def test_plan_rejects_duplicate_partition_in_manifest():
    manifest = _manifest(
        [
            (
                "nswgov",
                "sales",
                "normalized/nswgov/sales/period=20260907.csv",
                "5",
                "aaa",
            ),
            (
                "nswgov",
                "sales",
                "normalized/nswgov/sales/period=20260907.csv",
                "5",
                "bbb",
            ),
        ]
    )
    with pytest.raises(ValueError, match="twice"):
        plan_actions(manifest, {}, mode="partition")


# ----------------------------------------------------------------- header contract


def test_check_columns_lowercases_and_validates():
    assert check_columns(["series_id", "dim_REGION", "dim_REGION_label"]) == [
        "series_id",
        "dim_region",
        "dim_region_label",
    ]
    with pytest.raises(ValueError, match="not plain"):
        check_columns(["sale price"])
    with pytest.raises(ValueError, match="collides"):
        check_columns(["a", "_partition"])
    with pytest.raises(ValueError, match="duplicate"):
        check_columns(["Value", "value"])


def test_header_matches_ignores_loader_columns_but_not_order():
    existing = ["a", "b", *LOADER_COLUMNS]
    assert header_matches(existing, ["a", "b"])
    assert not header_matches(existing, ["b", "a"])
    assert not header_matches(existing, ["a", "b", "c"])


# ----------------------------------------------------------------- connection / dbt env


def test_database_url_requires_env(monkeypatch):
    for var in ENV_VARS.values():
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(DatabaseUnavailable, match="PROPERTYIQ_DATABASE_URL is not set"):
        database_url("owner")
    monkeypatch.setenv(
        "PROPERTYIQ_RO_DATABASE_URL",
        "postgresql+psycopg://propertyiq_ro:pw@localhost:5432/propertyiq",
    )
    assert database_url("ro") == "postgresql://propertyiq_ro:pw@localhost:5432/propertyiq"


def test_dbt_env_splits_owner_url():
    env = dbt_env("postgresql://propertyiq_owner:p%40ss@db.internal:6543/propertyiq")
    assert env["DBT_HOST"] == "db.internal"
    assert env["DBT_PORT"] == "6543"
    assert env["DBT_USER"] == "propertyiq_owner"
    assert env["DBT_PASSWORD"] == "p@ss"
    assert env["DBT_DBNAME"] == "propertyiq"
    with pytest.raises(ValueError):
        dbt_env("postgresql://localhost/")


def test_test_counts_reads_run_results(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    (target / "run_results.json").write_text(
        json.dumps(
            {
                "results": [
                    {"unique_id": "test.propertyiq.not_null_x", "status": "pass"},
                    {"unique_id": "test.propertyiq.unique_y", "status": "fail"},
                    {
                        "unique_id": "model.propertyiq.stg_property_sales",
                        "status": "success",
                    },
                ]
            }
        )
    )
    assert test_counts(tmp_path) == (1, 2)
    assert test_counts(tmp_path / "missing") == (None, None)


# ----------------------------------------------------------------- live: COPY round trip


@pytest.mark.live
def test_load_dataset_round_trip_against_central_postgres(tmp_path):
    """Create -> skip -> replace -> delete for a throwaway dataset in raw.zz_test_alpha."""

    if not os.environ.get("PROPERTYIQ_DATABASE_URL"):
        pytest.skip("PROPERTYIQ_DATABASE_URL not set")
    from propertyiq_getdata.core.manifest import file_sha256
    from propertyiq_getdata.db.connection import connect
    from propertyiq_getdata.db.load import load_dataset, load_state

    spec = LoadSpec("zz_test", "alpha", "unused", "partition")
    ddir = tmp_path / "normalized" / "zz_test" / "alpha"
    ddir.mkdir(parents=True)

    def write(name: str, body: str) -> tuple[str, str, int]:
        path = ddir / f"{name}.csv"
        path.write_text("id,Value,note\n" + body)
        rel = f"normalized/zz_test/alpha/{name}.csv"
        return rel, file_sha256(path), body.count("\n")

    def manifest(parts):
        return pd.DataFrame(
            [("zz_test", "alpha", rel, str(rows), sha) for rel, sha, rows in parts],
            columns=["source", "dataset", "path", "rows", "sha256"],
        )

    p1 = write("period=1", "1,10,\n2,,x\n")
    p2 = write("period=2", "3,30,\n")
    with connect("owner") as conn:
        try:
            first = load_dataset(
                conn,
                spec,
                data_dir=tmp_path,
                manifest=manifest([p1, p2]),
                log=lambda *_: None,
            )
            assert first["status"].tolist() == ["loaded", "loaded"]
            with conn.cursor() as cur:
                cur.execute("select id, value, note, _partition from raw.zz_test_alpha order by id")
                rows = cur.fetchall()
            assert rows == [
                ("1", "10", "", "period=1"),
                ("2", "", "x", "period=1"),
                ("3", "30", "", "period=2"),
            ]
            assert load_state(conn, "zz_test_alpha") == {
                "period=1": (p1[1], 2),
                "period=2": (p2[1], 1),
            }

            again = load_dataset(
                conn,
                spec,
                data_dir=tmp_path,
                manifest=manifest([p1, p2]),
                log=lambda *_: None,
            )
            assert again["status"].tolist() == ["skipped", "skipped"]

            p2b = write("period=2", "3,31,\n4,40,\n")
            third = load_dataset(
                conn,
                spec,
                data_dir=tmp_path,
                manifest=manifest([p2b]),
                log=lambda *_: None,
            )
            assert third[["partition", "status"]].values.tolist() == [
                ["period=2", "loaded"],
                ["period=1", "deleted"],
            ]
            with conn.cursor() as cur:
                cur.execute("select count(*), max(value) from raw.zz_test_alpha")
                assert cur.fetchone() == (2, "40")

            bad = tmp_path / "normalized" / "zz_test" / "alpha" / "period=3.csv"
            bad.write_text("id,other\n9,9\n")
            rel = "normalized/zz_test/alpha/period=3.csv"
            with pytest.raises(RuntimeError, match="do not match the CSV header"):
                load_dataset(
                    conn,
                    spec,
                    data_dir=tmp_path,
                    manifest=manifest([(rel, file_sha256(bad), 1)]),
                    log=lambda *_: None,
                )
        finally:
            with conn.cursor() as cur:
                cur.execute("drop table if exists raw.zz_test_alpha")
                cur.execute("delete from meta.load_state where table_name = 'zz_test_alpha'")
