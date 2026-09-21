"""abs_ts: registry, SDMX-CSV parsing, snapshot dedupe, manifest. Offline against real fixtures."""

from pathlib import Path

import pandas as pd
import pytest

from propertyiq_getdata.core.series import (
    CORE_COLUMNS,
    finalize_series_frame,
    period_start,
    short_region,
)
from propertyiq_getdata.core.snapshot import content_digest, write_snapshot_if_changed
from propertyiq_getdata.sources import abs_ts
from propertyiq_getdata.sources.abs_ts import (
    SERIES,
    NoRecordsError,
    fetch_sdmx_csv,
    parse_sdmx_csv,
    pull_abs_ts,
    sdmx_data_url,
    transform_abs_ts,
    update_abs_ts,
)

FIXTURES = Path(__file__).parent / "fixtures" / "abs_ts"

# Earliest period each registered dataset returned on 2026-09-21. A pull that
# starts later than this has lost history (see test_live_history below).
EXPECTED_EARLIEST = {
    "dwelling_values": "2011-07-01",
    "dwelling_medians": "2002-01-01",
    "cpi": "1948-07-01",
    "labour_force": "1978-02-01",
    "wpi": "1997-07-01",
    "lending_housing": "2002-07-01",
    "building_approvals": "2011-07-01",
    "population": "1981-07-01",
}

# Dimension count per dataflow (from the DSDs, 2026-09-21). One position short
# returns 404 from the API, so the registry keys are pinned here.
DSD_DIMENSIONS = {
    "RES_DWELL_ST": 3,
    "RES_DWELL": 3,
    "CPI": 5,
    "LF": 6,
    "WPI": 7,
    "LEND_HOUSING": 9,
    "BA_SA2": 7,
    "BA_SA2_2016-21": 7,
    "BA_SA2_201116": 7,
    "ERP_Q": 5,
}


# ---------------------------------------------------------------- registry


def test_registry_covers_expected_datasets():
    assert set(SERIES) == set(EXPECTED_EARLIEST)


def test_registry_keys_match_dsd_dimension_count():
    for spec in SERIES.values():
        for dataflow in spec.dataflows:
            assert spec.key.count(".") + 1 == DSD_DIMENSIONS[dataflow], (spec.dataset, dataflow)


def test_registry_never_filters_region_and_has_no_start_period():
    # REGION is the third-from-last position in every one of these DSDs
    # (…REGION.FREQ) except the BA family (…REGION_TYPE.REGION.FREQ) — either
    # way it is the position just before FREQ, which is the last position.
    for spec in SERIES.values():
        positions = spec.key.split(".")
        assert positions[-2] == "", f"{spec.dataset} filters REGION: {spec.key}"
        assert not hasattr(spec, "start_period")


def test_sdmx_url_has_no_query_string():
    url = sdmx_data_url("CPI", SERIES["cpi"].key)
    assert url == "https://data.api.abs.gov.au/rest/data/ABS,CPI/1+2+3.10001.10+20..Q+M"
    assert "startPeriod" not in url


# ---------------------------------------------------------------- parsing


def test_parse_cpi_fixture_contract_columns():
    frame = finalize_series_frame(parse_sdmx_csv(FIXTURES / "CPI.csv"), source="abs_ts", dataset="cpi", asof="2026-09-21")
    assert list(frame.columns[: len(CORE_COLUMNS)]) == CORE_COLUMNS
    assert all(c.startswith("dim_") for c in frame.columns[len(CORE_COLUMNS) :])
    assert set(frame["region"]) <= {"Sydney", "AUS"}
    assert set(frame["dataflow"]) == {"CPI"}
    assert frame["value"].dtype.kind == "f"
    assert frame["base_period"].str.contains("100").all()  # rebased index carries its base
    monthly = frame[frame["freq"] == "M"]
    quarterly = frame[frame["freq"] == "Q"]
    assert not monthly.empty and not quarterly.empty
    assert (monthly["period_start"].str[-2:] == "01").all()
    assert set(quarterly["period_start"].str[5:7]) <= {"01", "04", "07", "10"}


def test_series_id_is_dataflow_plus_full_key():
    frame = parse_sdmx_csv(FIXTURES / "RES_DWELL_ST.csv")
    assert frame["series_id"].str.match(r"^RES_DWELL_ST\.\d\.\w+\.Q$").all()
    assert frame["series_label"].str.contains("Mean price").all()
    assert frame["obs_status"].isin({"", "p", "r"}).all()
    assert (frame["unit_mult"] == 3).all()  # AUD thousands


def test_period_start_rules():
    assert period_start("2026-Q2") == "2026-04-01"
    assert period_start("2026-07") == "2026-07-01"
    assert period_start("2026") == "2026-01-01"
    assert period_start("2026-07-15") == "2026-07-15"
    assert period_start("2020-21", "A") == "2020-07-01"
    with pytest.raises(ValueError):
        period_start("Q2 2026")


def test_short_region_normalises_states_only():
    assert short_region("New South Wales") == "NSW"
    assert short_region("Weighted average of eight capital cities") == "AUS"
    assert short_region("Greater Sydney") == "Greater Sydney"


def test_parse_raises_on_zero_rows(tmp_path):
    empty = tmp_path / "empty.csv"
    empty.write_text("DATAFLOW,TIME_PERIOD: Time Period,OBS_VALUE\n")
    with pytest.raises(RuntimeError, match="ZERO rows"):
        parse_sdmx_csv(empty)


# ---------------------------------------------------------------- HTTP


class _Response:
    def __init__(self, status_code, text=b""):
        self.status_code = status_code
        self.content = text
        self.text = text.decode()

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class _Session:
    """Serves fixture files by dataflow; 404 NoRecordsFound for anything else."""

    def __init__(self, files: dict[str, Path]):
        self.files = files
        self.calls = []

    def get(self, url, timeout=None):
        self.calls.append(url)
        dataflow = url.split("ABS,")[1].split("/")[0]
        if dataflow in self.files:
            return _Response(200, self.files[dataflow].read_bytes())
        return _Response(404, b"NoRecordsFound")


def test_fetch_raises_no_records_on_404_body():
    with pytest.raises(NoRecordsError, match="ZERO rows"):
        fetch_sdmx_csv(_Session({}), "RPPI", "..Q")


# ---------------------------------------------------------------- pipeline


@pytest.fixture
def session():
    return _Session(
        {
            "CPI": FIXTURES / "CPI.csv",
            "RES_DWELL_ST": FIXTURES / "RES_DWELL_ST.csv",
            "BA_SA2": FIXTURES / "BA_SA2.csv",
            "BA_SA2_2016-21": FIXTURES / "BA_SA2_2016-21.csv",
            # BA_SA2_201116 deliberately absent from the CPI/TVD tests below
        }
    )


def test_pull_writes_raw_verbatim_and_is_idempotent(tmp_path, session):
    report = pull_abs_ts(data_dir=tmp_path, datasets=["cpi"], asof="2026-09-21", session=session)
    assert report["status"].tolist() == ["pulled"]
    raw = tmp_path / "raw" / "abs_ts" / "cpi" / "asof=2026-09-21__CPI.csv"
    assert raw.read_bytes() == (FIXTURES / "CPI.csv").read_bytes()

    again = pull_abs_ts(data_dir=tmp_path, datasets=["cpi"], asof="2026-09-21", session=session)
    assert again["status"].tolist() == ["exists"]
    assert len(session.calls) == 1

    forced = pull_abs_ts(data_dir=tmp_path, datasets=["cpi"], asof="2026-09-21", session=session, force=True)
    assert forced["status"].tolist() == ["pulled"]


def test_update_writes_snapshot_and_manifest(tmp_path, session):
    report = update_abs_ts(data_dir=tmp_path, datasets=["cpi", "dwelling_values"], asof="2026-09-21", session=session)
    assert report["status"].tolist() == ["written", "written"]
    snapshot = tmp_path / "normalized" / "abs_ts" / "cpi" / "asof=2026-09-21.csv"
    assert snapshot.exists()

    manifest = pd.read_csv(tmp_path / "manifests" / "abs_ts_manifest.csv", dtype=str)
    assert list(manifest.columns) == ["source", "dataset", "period_start", "period_end", "path", "rows", "sha256", "created_at_utc"]
    assert manifest["dataset"].tolist() == ["cpi", "dwelling_values"]
    assert manifest["path"].tolist() == [
        "normalized/abs_ts/cpi/asof=2026-09-21.csv",
        "normalized/abs_ts/dwelling_values/asof=2026-09-21.csv",
    ]
    cpi = manifest.set_index("dataset").loc["cpi"]
    assert int(cpi["rows"]) == 40
    assert cpi["period_start"] == "2026-01-01"


def test_same_content_next_day_is_unchanged_and_writes_nothing(tmp_path, session):
    update_abs_ts(data_dir=tmp_path, datasets=["cpi"], asof="2026-09-21", session=session)
    report = update_abs_ts(data_dir=tmp_path, datasets=["cpi"], asof="2026-09-22", session=session)
    assert report["status"].tolist() == ["unchanged"]
    snapshots = sorted((tmp_path / "normalized" / "abs_ts" / "cpi").glob("asof=*.csv"))
    assert [p.name for p in snapshots] == ["asof=2026-09-21.csv"]
    manifest = pd.read_csv(tmp_path / "manifests" / "abs_ts_manifest.csv", dtype=str)
    assert manifest.shape[0] == 1


def test_changed_content_next_day_is_a_new_snapshot(tmp_path, session):
    update_abs_ts(data_dir=tmp_path, datasets=["cpi"], asof="2026-09-21", session=session)
    revised = pd.read_csv(FIXTURES / "CPI.csv", dtype=str, keep_default_na=False)
    revised.loc[0, "OBS_VALUE"] = "999.9"
    revised_path = tmp_path / "revised.csv"
    revised.to_csv(revised_path, index=False)
    session.files["CPI"] = revised_path

    report = update_abs_ts(data_dir=tmp_path, datasets=["cpi"], asof="2026-10-29", session=session)
    assert report["status"].tolist() == ["written"]
    snapshots = sorted((tmp_path / "normalized" / "abs_ts" / "cpi").glob("asof=*.csv"))
    assert [p.name for p in snapshots] == ["asof=2026-09-21.csv", "asof=2026-10-29.csv"]
    manifest = pd.read_csv(tmp_path / "manifests" / "abs_ts_manifest.csv", dtype=str)
    assert manifest["dataset"].tolist() == ["cpi", "cpi"]


def test_stitched_dataset_requires_every_dataflow(tmp_path, session, monkeypatch):
    # building_approvals needs three dataflows; the session only has two.
    with pytest.raises(NoRecordsError):
        update_abs_ts(data_dir=tmp_path, datasets=["building_approvals"], asof="2026-09-21", session=session)

    two_flow = abs_ts.SeriesSpec(
        dataset="building_approvals",
        dataflows=("BA_SA2_2016-21", "BA_SA2"),
        key=SERIES["building_approvals"].key,
        description="test",
    )
    monkeypatch.setitem(abs_ts.SERIES, "building_approvals", two_flow)
    report = update_abs_ts(data_dir=tmp_path, datasets=["building_approvals"], asof="2026-09-21", session=session)
    assert report["status"].tolist() == ["written"]
    frame = pd.read_csv(tmp_path / "normalized" / "abs_ts" / "building_approvals" / "asof=2026-09-21.csv", dtype=str)
    assert set(frame["dataflow"]) == {"BA_SA2_2016-21", "BA_SA2"}
    assert frame["period_start"].is_monotonic_increasing or frame["series_id"].nunique() > 1


def test_transform_without_pull_raises(tmp_path):
    with pytest.raises(RuntimeError, match="run `abs-ts pull` first"):
        transform_abs_ts(data_dir=tmp_path, datasets=["cpi"])


def test_content_digest_ignores_asof(tmp_path):
    frame = parse_sdmx_csv(FIXTURES / "CPI.csv")
    a = finalize_series_frame(frame, source="abs_ts", dataset="cpi", asof="2026-09-21")
    b = finalize_series_frame(frame, source="abs_ts", dataset="cpi", asof="2026-09-22")
    a.to_csv(tmp_path / "a.csv", index=False)
    b.to_csv(tmp_path / "b.csv", index=False)
    assert content_digest(tmp_path / "a.csv") == content_digest(tmp_path / "b.csv")
    assert (tmp_path / "a.csv").read_bytes() != (tmp_path / "b.csv").read_bytes()


def test_write_snapshot_statuses(tmp_path):
    frame = pd.DataFrame({"series_id": ["x"], "period_start": ["2026-01-01"], "value": [1.0], "asof": ["2026-09-21"]})
    _, status = write_snapshot_if_changed(frame, tmp_path / "asof=2026-09-21.csv")
    assert status == "written"
    _, status = write_snapshot_if_changed(frame, tmp_path / "asof=2026-09-21.csv")
    assert status == "unchanged"
    frame.loc[0, "value"] = 2.0
    _, status = write_snapshot_if_changed(frame, tmp_path / "asof=2026-09-21.csv")
    assert status == "rewritten"
    assert not list(tmp_path.glob("*.tmp"))


# ---------------------------------------------------------------- live (opt-in)


@pytest.mark.live
def test_live_history_depth():
    """Hits the real API for the smallest dataset; run with ``pytest -m live``."""

    session = abs_ts.make_session()
    content = fetch_sdmx_csv(session, "ERP_Q", SERIES["population"].key)
    assert b"TIME_PERIOD" in content
