"""rba: header-block parsing, Series-ID keyed columns, date formats, snapshot pipeline. Offline."""

from pathlib import Path

import pandas as pd
import pytest

from propertyiq_getdata.core.series import CORE_COLUMNS
from propertyiq_getdata.sources.rba import (
    TABLES,
    parse_rba_csv,
    pull_rba,
    rba_csv_url,
    transform_rba,
    update_rba,
)

FIXTURES = Path(__file__).parent / "fixtures" / "rba"


def test_registry_and_urls():
    assert set(TABLES) == {"rba_cash_rate", "rba_lending_rates", "rba_rate_changes"}
    assert rba_csv_url("f1.1") == "https://www.rba.gov.au/statistics/tables/csv/f1.1-data.csv"


def test_parse_f5_keys_columns_by_series_id_and_month_start():
    frame = parse_rba_csv(FIXTURES / "f5.csv", table="f5")
    assert "FILRHLBVS" in set(frame["series_id"])  # banks variable standard owner-occupier
    owner_occ = frame[frame["series_id"] == "FILRHLBVS"]
    assert owner_occ["series_label"].iloc[0] == "Lending rates; Housing loans; Banks; Variable; Standard; Owner-occupier"
    assert (owner_occ["freq"] == "M").all()
    assert (owner_occ["period_start"].str[-2:] == "01").all()  # 31/08/2026 -> 2026-08-01
    assert owner_occ["time_period"].str.match(r"^\d{2}/\d{2}/\d{4}$").all()
    assert (owner_occ["unit"] == "Per cent per annum").all()
    assert (frame["region"] == "AUS").all()
    assert frame["value"].notna().all()  # empty cells are dropped, not NaN rows


def test_parse_f1_1_see_notes_columns_inherit_monthly():
    frame = parse_rba_csv(FIXTURES / "f1.1.csv", table="f1.1")
    assert set(frame["freq"]) == {"M"}
    assert "FIRMMCRT" in set(frame["series_id"])


def test_parse_a2_event_dates_and_range_text():
    frame = parse_rba_csv(FIXTURES / "a2.csv", table="a2")
    assert set(frame["freq"]) == {"E"}
    assert frame["period_start"].iloc[0] == "1990-01-23"  # DD-MMM-YYYY, kept as the event date
    ranged = frame[frame["value"].isna()]
    assert not ranged.empty
    assert ranged["obs_comment"].str.contains(" to ").all()
    numeric = frame[frame["value"].notna()]
    assert (numeric["obs_comment"] == "").all()


def test_parse_raises_without_series_id_row(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("F5 SOMETHING\nTitle,a,b\n31/01/2026,1,2\n")
    with pytest.raises(RuntimeError, match="Series ID"):
        parse_rba_csv(bad)


class _Response:
    def __init__(self, content):
        self.status_code = 200
        self.content = content

    def raise_for_status(self):
        pass


class _Session:
    def __init__(self):
        self.calls = []

    def get(self, url, timeout=None):
        self.calls.append(url)
        table = url.rsplit("/", 1)[1].replace("-data.csv", "")
        return _Response((FIXTURES / f"{table}.csv").read_bytes())


def test_update_pipeline_contract_and_dedupe(tmp_path):
    session = _Session()
    report = update_rba(data_dir=tmp_path, asof="2026-09-21", session=session)
    assert report["status"].tolist() == ["written"] * 3
    assert len(session.calls) == 3

    snapshot = pd.read_csv(tmp_path / "normalized" / "rba" / "rba_cash_rate" / "asof=2026-09-21.csv", dtype=str)
    assert list(snapshot.columns) == CORE_COLUMNS  # RBA adds no dim_* columns
    assert set(snapshot["source"]) == {"rba"}
    assert set(snapshot["dataflow"]) == {"f1.1"}

    manifest = pd.read_csv(tmp_path / "manifests" / "rba_manifest.csv", dtype=str)
    assert manifest["dataset"].tolist() == ["rba_cash_rate", "rba_lending_rates", "rba_rate_changes"]
    assert manifest["path"].str.match(r"^normalized/rba/[a-z_]+/asof=2026-09-21\.csv$").all()

    again = update_rba(data_dir=tmp_path, asof="2026-09-28", session=session)
    assert again["status"].tolist() == ["unchanged"] * 3
    assert not list((tmp_path / "normalized" / "rba").rglob("asof=2026-09-28.csv"))


def test_pull_is_idempotent_per_asof(tmp_path):
    session = _Session()
    pull_rba(data_dir=tmp_path, datasets=["rba_rate_changes"], asof="2026-09-21", session=session)
    report = pull_rba(data_dir=tmp_path, datasets=["rba_rate_changes"], asof="2026-09-21", session=session)
    assert report["status"].tolist() == ["exists"]
    assert len(session.calls) == 1


def test_transform_without_pull_raises(tmp_path):
    with pytest.raises(RuntimeError, match="run `rba pull` first"):
        transform_rba(data_dir=tmp_path, datasets=["rba_cash_rate"])
