import zipfile
from io import BytesIO

import openpyxl
import pandas as pd
import pytest

from propertyiq_getdata.core.paths import get_paths
from propertyiq_getdata.sources.abs import (
    TABLE_CSV_RE,
    abs_interim_dir,
    abs_poa_columns_path,
    abs_poa_partition_path,
    extract_abs,
    poa_code_to_postcode,
    pull_abs,
    raw_datapack_zip_path,
    raw_extract_dir,
    transform_abs,
)


def _fake_table_csvs() -> dict[str, str]:
    return {
        # G01 and G02 both define a "Tot_P" short code — a real collision seen in
        # the actual 2021 GCP DataPack (415 short codes repeat across tables).
        "2021Census_G01_NSW_POA.csv": "POA_CODE_2021,Tot_P\nPOA2000,100\nPOA2007,50\n",
        "2021Census_G02_NSW_POA.csv": "POA_CODE_2021,Tot_P,Median_age_persons\nPOA2000,200,32\nPOA2007,90,41\n",
    }


def _fake_metadata_workbook_bytes() -> bytes:
    workbook = openpyxl.Workbook()
    table_sheet = workbook.active
    table_sheet.title = "Table Number, Name, Population"
    for _ in range(6):
        table_sheet.append([None, None, None])
    table_sheet.append(["2021 Census of Population and Housing"])
    table_sheet.append(["General Community Profile Tables"])
    table_sheet.append(["Table Number", "Table Name", "Table population "])
    table_sheet.append(["G01", "Selected Person Characteristics by Sex", "Persons"])
    table_sheet.append(["G02", "Selected Medians and Averages", None])

    cell_sheet = workbook.create_sheet("Cell Descriptors Information")
    for _ in range(6):
        cell_sheet.append([None] * 6)
    cell_sheet.append(["2021 Census of Population and Housing"])
    cell_sheet.append(["General Community Profile DataPack Metadata"])
    cell_sheet.append([None, None, "Celldescriptors"])
    cell_sheet.append(["Sequential", "Short", "Long", "DataPackfile", "Profiletable", "Columnheadingdescriptioninprofile"])
    cell_sheet.append(["G1", "Tot_P", "Total_Persons", "G01", "G01", "Persons"])
    cell_sheet.append(["G2", "Tot_P", "Total_Persons", "G02", "G02", "Persons"])
    cell_sheet.append(["G3", "Median_age_persons", "Median_age_of_persons", "G02", "G02", "Median age"])

    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def write_fake_datapack(extract_dir) -> None:
    table_dir = extract_dir / "2021 Census GCP Postal Areas for NSW"
    table_dir.mkdir(parents=True, exist_ok=True)
    for name, content in _fake_table_csvs().items():
        (table_dir / name).write_text(content, encoding="utf-8")
    metadata_dir = extract_dir / "Metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    (metadata_dir / "Metadata_2021_GCP_DataPack_R1_R2.xlsx").write_bytes(_fake_metadata_workbook_bytes())


def build_fake_datapack_zip_bytes() -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as zip_file:
        for name, content in _fake_table_csvs().items():
            zip_file.writestr(f"2021 Census GCP Postal Areas for NSW/{name}", content)
        zip_file.writestr("Metadata/Metadata_2021_GCP_DataPack_R1_R2.xlsx", _fake_metadata_workbook_bytes())
    return buffer.getvalue()


def test_poa_code_to_postcode_strips_prefix_and_zero_pads():
    assert poa_code_to_postcode("POA2000") == "2000"
    assert poa_code_to_postcode("POA800") == "0800"
    with pytest.raises(ValueError):
        poa_code_to_postcode("LGA14000")


def test_table_csv_re_matches_sub_lettered_tables():
    assert TABLE_CSV_RE.match("2021Census_G01_NSW_POA.csv").group("table") == "G01"
    assert TABLE_CSV_RE.match("2021Census_G04A_NSW_POA.csv").group("table") == "G04A"
    assert TABLE_CSV_RE.match("2021Census_G01_NSW_LGA.csv").group("geography") == "LGA"
    assert TABLE_CSV_RE.match("2021Census_geog_desc.csv") is None


def test_extract_abs_writes_one_interim_csv_per_table_with_postcode_column(tmp_path):
    data_dir = tmp_path / "data"
    write_fake_datapack(raw_extract_dir(data_dir, 2021, "NSW", "POA"))

    status = extract_abs(data_dir=data_dir, census_year=2021, state="NSW", geography="POA")

    assert sorted(status["table"]) == ["G01", "G02"]
    g01 = pd.read_csv(abs_interim_dir(data_dir, 2021, "NSW", "POA") / "G01.csv", dtype=str)
    assert list(g01.columns) == ["Tot_P", "postcode"]
    assert g01.set_index("postcode")["Tot_P"].to_dict() == {"2000": "100", "2007": "50"}


def test_transform_abs_namespaces_colliding_short_codes_and_decodes_labels(tmp_path):
    data_dir = tmp_path / "data"
    write_fake_datapack(raw_extract_dir(data_dir, 2021, "NSW", "POA"))
    extract_abs(data_dir=data_dir, census_year=2021, state="NSW", geography="POA")

    result = transform_abs(data_dir=data_dir, census_year=2021, state="NSW", geography="POA")

    wide = pd.read_csv(abs_poa_partition_path(data_dir, 2021), dtype=str)
    assert result["rows"].tolist() == [2]
    assert set(wide.columns) == {"postcode", "census_year", "G01__Tot_P", "G02__Tot_P", "G02__Median_age_persons"}
    row = wide.set_index("postcode").loc["2000"]
    assert row["G01__Tot_P"] == "100"
    assert row["G02__Tot_P"] == "200"
    assert row["G02__Median_age_persons"] == "32"

    columns = pd.read_csv(abs_poa_columns_path(data_dir, 2021)).set_index("column")
    assert columns.loc["G01__Tot_P", "long_label"] == "Total_Persons"
    assert columns.loc["G01__Tot_P", "table_name"] == "Selected Person Characteristics by Sex"
    assert columns.loc["G02__Tot_P", "table_name"] == "Selected Medians and Averages"

    manifest = pd.read_csv(get_paths(data_dir).abs_poa_manifest, dtype=str)
    assert manifest["dataset"].tolist() == ["poa_gcp"]
    assert manifest["rows"].tolist() == ["2"]


class FakeAbsResponse:
    def __init__(self, content: bytes):
        self.content = content

    def raise_for_status(self):
        return None


class FakeAbsSession:
    def __init__(self, content: bytes):
        self.content = content
        self.calls = 0

    def get(self, url, timeout):
        self.calls += 1
        return FakeAbsResponse(self.content)


def test_pull_abs_downloads_once_then_skips_when_already_extracted(tmp_path):
    data_dir = tmp_path / "data"
    session = FakeAbsSession(build_fake_datapack_zip_bytes())

    first = pull_abs(data_dir=data_dir, census_year=2021, state="NSW", geography="POA", session=session)
    assert first["status"].tolist() == ["downloaded"]
    assert session.calls == 1
    assert raw_datapack_zip_path(data_dir, 2021, "NSW", "POA").exists()
    extracted_csv = (
        raw_extract_dir(data_dir, 2021, "NSW", "POA") / "2021 Census GCP Postal Areas for NSW" / "2021Census_G01_NSW_POA.csv"
    )
    assert extracted_csv.exists()

    second = pull_abs(data_dir=data_dir, census_year=2021, state="NSW", geography="POA", session=session)
    assert second["status"].tolist() == ["exists"]
    assert session.calls == 1


def test_pull_abs_dry_run_does_not_download(tmp_path):
    data_dir = tmp_path / "data"
    session = FakeAbsSession(build_fake_datapack_zip_bytes())

    status = pull_abs(data_dir=data_dir, census_year=2021, state="NSW", geography="POA", dry_run=True, session=session)

    assert status["status"].tolist() == ["pending"]
    assert session.calls == 0
    assert not raw_datapack_zip_path(data_dir, 2021, "NSW", "POA").exists()
