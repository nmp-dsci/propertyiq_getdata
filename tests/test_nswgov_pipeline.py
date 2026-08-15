import pandas as pd

import datetime as dt

import pytest
from types import SimpleNamespace

from propertyiq_getdata.sources.nswgov import (
    ProbeError,
    candidate_links,
    discover_links,
    probe_links,
    filter_new_links,
    infer_dat_ymd,
    normalise_ymd,
    parse_dat_file,
    transform_etl2_frame,
    transform_nswgov,
)


def test_discover_links_uses_url_shape_not_button_class():
    html = """
    <a class="btn btn-primary btn-sales-data btn-sales-data"
       href="https://www.valuergeneral.nsw.gov.au/__psi/weekly/20260629.zip">Weekly</a>
    <a class="changed-class"
       href="https://www.valuergeneral.nsw.gov.au/__psi/yearly/2025.zip">Yearly</a>
    """

    links = discover_links(html)

    assert set(links["term"]) == {"weekly", "yearly"}
    assert links.set_index("period").loc["20260629", "term"] == "weekly"
    assert links.set_index("period").loc["2025", "term"] == "yearly"


def test_filter_new_links_keeps_current_year_archive_and_new_weeklies():
    links = pd.DataFrame(
        [
            {"term": "yearly", "period": "2023", "href": "old"},
            {"term": "yearly", "period": "2024", "href": "current-year"},
            {"term": "yearly", "period": "2025", "href": "next-year"},
            {"term": "weekly", "period": "20240923", "href": "processed"},
            {"term": "weekly", "period": "20241007", "href": "new"},
        ]
    )

    filtered = filter_new_links(links, latest_period="20240930")

    assert filtered["href"].tolist() == ["current-year", "next-year", "new"]


def test_normalise_ymd_handles_current_dat_filename_date_order(tmp_path):
    dat_path = tmp_path / "weekly" / "20260601" / "001_SALES_DATA_NNME_01062026.DAT"
    dat_path.parent.mkdir(parents=True)
    dat_path.write_text("", encoding="latin1")

    assert normalise_ymd("01062026") == "20260601"
    assert infer_dat_ymd(dat_path) == "20260601"


def test_parse_dat_file_and_transform_to_final_schema(tmp_path):
    dat_path = tmp_path / "001_SALES_DATA_NNME_20260105.DAT"
    dat_path.write_text(
        "\n".join(
            [
                "A;S;001;20260105;user",
                "B;001;12345;1;20260105 01:10;PROP NAME;2;10;HIGH ST;SYDNEY;2000;100;M;20251201;20251215;1500000;R2;R;RESIDENCE;99;AAO;;0;DN1",
                "Z;3;1;0;0",
            ]
        ),
        encoding="latin1",
    )

    extracted = parse_dat_file(dat_path)
    wide = transform_etl2_frame(extracted, fn_src="20260105.csv")

    assert extracted.query('record_type == "B" and label == "sale_price"')["value"].iloc[0] == "1500000"
    assert list(wide.columns)[:4] == ["file", "fn_src", "ymd", "index"]
    assert wide.loc[0, "postcode"] == "2000"
    assert wide.loc[0, "sale_price"] == "1500000"
    assert wide.loc[0, "ymd"] == "20260105"


def test_transform_nswgov_writes_only_missing_partitions(tmp_path):
    data_dir = tmp_path / "data"
    etl2_dir = data_dir / "interim" / "nswgov" / "output_etl2"
    etl2_dir.mkdir(parents=True)
    existing_partition = data_dir / "normalized" / "nswgov" / "sales" / "period=20250101.csv"
    existing_partition.parent.mkdir(parents=True)
    existing_partition.write_text(
        "file,fn_src,ymd,index,area_sqm,area_type,component_cd,contract_dt,create_dt,dealing_no,district_code,house_no,locality,postcode,prop_name,prop_nature,prop_purpose,property_id,record_type,sale_cd,sale_counter,sale_interest,sale_price,settle_dt,strata_no,street_name,unit_no,zoning\n"
        "old.DAT,20250101.csv,20250101,1,,,,20250101,20250101 01:10,,1,1,SYDNEY,2000,,R,RESIDENCE,1,B,,1,0,1,20250102,,,,\n",
        encoding="utf-8",
    )

    existing = pd.DataFrame(
        [
            {
                "record_type": "B",
                "index": 1,
                "variable": 15,
                "value": "1",
                "label": "sale_price",
                "ymd": "20250101",
                "file": "old.DAT",
            }
        ]
    )
    new = pd.DataFrame(
        [
            {
                "record_type": "B",
                "index": 2,
                "variable": 15,
                "value": "2000000",
                "label": "sale_price",
                "ymd": "20260105",
                "file": "new.DAT",
            },
            {
                "record_type": "B",
                "index": 2,
                "variable": 10,
                "value": "2000",
                "label": "postcode",
                "ymd": "20260105",
                "file": "new.DAT",
            },
        ]
    )
    existing.to_csv(etl2_dir / "20250101.csv", index=False)
    new.to_csv(etl2_dir / "20260105.csv", index=False)

    status = transform_nswgov(data_dir=data_dir)
    result = pd.read_csv(data_dir / "normalized" / "nswgov" / "sales" / "period=20260105.csv", dtype=str)
    manifest = pd.read_csv(data_dir / "manifests" / "nswgov_sales_manifest.csv", dtype=str)

    assert status["period"].tolist() == ["20260105"]
    assert result["fn_src"].tolist() == ["20260105.csv"]
    assert result.loc[0, "sale_price"] == "2000000"
    assert manifest["period_end"].tolist() == ["2025-01-01", "2026-01-05"]


class TestCandidateLinks:
    """Discovery is now enumerate-and-probe: the server's directory index is
    403, but archive names are entirely predictable, so the candidate set is
    generated locally and confirmed with HEAD requests."""

    TODAY = dt.date(2026, 8, 15)

    def test_weekly_candidates_are_mondays(self):
        links = candidate_links(
            ("weekly",), since=dt.date(2026, 6, 29), today=self.TODAY
        )
        periods = links["period"].tolist()
        assert periods == ["20260706", "20260713", "20260720", "20260727", "20260803", "20260810"]
        for period in periods:
            assert dt.datetime.strptime(period, "%Y%m%d").weekday() == 0

    def test_weekly_excludes_the_watermark_itself(self):
        links = candidate_links(("weekly",), since=dt.date(2026, 6, 29), today=self.TODAY)
        assert "20260629" not in links["period"].tolist(), "already-collected period must not re-list"

    def test_hrefs_follow_the_psi_layout(self):
        links = candidate_links(("weekly",), since=dt.date(2026, 6, 29), today=self.TODAY)
        assert links.iloc[0]["href"] == (
            "https://www.valuergeneral.nsw.gov.au/__psi/weekly/20260706.zip"
        )
        yearly = candidate_links(("yearly",), since=dt.date(2025, 1, 1), today=self.TODAY)
        assert yearly.iloc[0]["href"] == (
            "https://www.valuergeneral.nsw.gov.au/__psi/yearly/2025.zip"
        )

    def test_no_since_scans_from_the_first_published_period(self):
        links = candidate_links(("weekly",), today=dt.date(2012, 1, 30))
        assert links["period"].tolist() == ["20120102", "20120109", "20120116", "20120123", "20120130"]

    def test_yearly_candidates_span_to_the_current_year(self):
        links = candidate_links(("yearly",), today=self.TODAY)
        years = links["period"].tolist()
        assert years[0] == "2001" and years[-1] == "2026"

    def test_terms_are_honoured(self):
        assert set(candidate_links(("weekly",), today=self.TODAY)["term"]) == {"weekly"}
        assert set(candidate_links(("yearly",), today=self.TODAY)["term"]) == {"yearly"}
        both = set(candidate_links(("weekly", "yearly"), today=self.TODAY)["term"])
        assert both == {"weekly", "yearly"}

    def test_empty_when_nothing_is_due(self):
        links = candidate_links(("weekly",), since=dt.date(2026, 8, 10), today=dt.date(2026, 8, 12))
        assert links.empty
        assert list(links.columns) == ["term", "period", "href"]


class TestProbeLinks:
    """A period that is not published yet answers 404 - that is how the scan
    finds the end of the data instead of guessing a cutoff."""

    class FakeSession:
        def __init__(self, published):
            self.published = set(published)
            self.asked = []

        def head(self, href, timeout=None):
            self.asked.append(href)
            code = 200 if href in self.published else 404
            return SimpleNamespace(status_code=code)

    def test_keeps_only_published_periods(self):
        candidates = candidate_links(("weekly",), since=dt.date(2026, 6, 29), today=dt.date(2026, 8, 15))
        published = candidates["href"].tolist()[:3]
        session = self.FakeSession(published)

        found = probe_links(candidates, session=session)

        assert found["period"].tolist() == ["20260706", "20260713", "20260720"]
        assert len(session.asked) == len(candidates), "every candidate is probed"

    def test_a_transport_error_raises_rather_than_dropping_periods(self):
        """A dropped connection is *unknown*, not 404. Folding the two together
        would silently lose real weeks of sales on a flaky network while still
        reporting success."""

        class Boom:
            def __init__(self):
                self.calls = 0

            def head(self, href, timeout=None):
                self.calls += 1
                raise OSError("connection reset")

        candidates = candidate_links(("weekly",), since=dt.date(2026, 6, 29), today=dt.date(2026, 8, 15))
        session = Boom()
        with pytest.raises(ProbeError, match="could not determine whether"):
            probe_links(candidates, session=session, attempts=3)
        assert session.calls == 3, "each probe is retried before giving up"

    def test_a_flaky_probe_recovers_within_its_retries(self):
        class Flaky:
            def __init__(self):
                self.calls = 0

            def head(self, href, timeout=None):
                self.calls += 1
                if self.calls == 1:
                    raise OSError("connection reset")
                return SimpleNamespace(status_code=200)

        candidates = candidate_links(("weekly",), since=dt.date(2026, 8, 3), today=dt.date(2026, 8, 15))
        found = probe_links(candidates, session=Flaky(), attempts=3)
        assert found["period"].tolist() == ["20260810"]

    def test_empty_candidates_short_circuit(self):
        empty = candidate_links(("weekly",), since=dt.date(2026, 8, 10), today=dt.date(2026, 8, 12))
        session = self.FakeSession([])
        assert probe_links(empty, session=session).empty
        assert session.asked == [], "no candidates means no network calls"
