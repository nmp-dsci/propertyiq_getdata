"""`db` CLI group: parsing and dispatch to the pipeline functions. Offline."""

from __future__ import annotations

import pandas as pd

from propertyiq_getdata import cli


def test_db_parser_stages_and_flags():
    parser = cli.build_parser()
    args = parser.parse_args(
        [
            "db",
            "load",
            "--dataset",
            "rba",
            "--dataset",
            "abs_ts/cpi",
            "--full-refresh",
            "--dry-run",
        ]
    )
    assert (args.command, args.stage) == ("db", "load")
    assert args.dataset == ["rba", "abs_ts/cpi"]
    assert args.full_refresh and args.dry_run
    assert parser.parse_args(["db", "dbt"]).target == "all"
    assert parser.parse_args(["db", "dbt", "build"]).target == "build"
    assert parser.parse_args(["db", "export-fixture", "--limit", "10"]).limit == 10


def test_db_update_dispatch(monkeypatch, capsys):
    calls = {}

    def fake_update(**kwargs):
        calls.update(kwargs)
        return pd.DataFrame([{"table": "abs_ts_cpi", "status": "loaded"}])

    monkeypatch.setattr("propertyiq_getdata.db.update_db", fake_update)
    assert cli.main(["db", "update", "--data-dir", "/tmp/x", "--dataset", "abs_ts"]) == 0
    assert calls == {
        "data_dir": "/tmp/x",
        "datasets": ["abs_ts"],
        "full_refresh": False,
        "dry_run": False,
    }
    assert "abs_ts_cpi" in capsys.readouterr().out


def test_db_smoke_exit_code(monkeypatch):
    monkeypatch.setattr("propertyiq_getdata.db.smoke", lambda: False)
    assert cli.main(["db", "smoke"]) == 1
    monkeypatch.setattr("propertyiq_getdata.db.smoke", lambda: True)
    assert cli.main(["db", "smoke"]) == 0
