import csv
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


NSWGOV_COLUMNS = [
    "file",
    "fn_src",
    "ymd",
    "index",
    "area_sqm",
    "area_type",
    "component_cd",
    "contract_dt",
    "create_dt",
    "dealing_no",
    "district_code",
    "house_no",
    "locality",
    "postcode",
    "prop_name",
    "prop_nature",
    "prop_purpose",
    "property_id",
    "record_type",
    "sale_cd",
    "sale_counter",
    "sale_interest",
    "sale_price",
    "settle_dt",
    "strata_no",
    "street_name",
    "unit_no",
    "zoning",
]

RENTBOARD_COLUMNS = ["lodgement_dt", "postcode", "property_type", "bedrooms", "weekly_rent"]


def summarize_csv(path, date_column):
    if not path.exists():
        pytest.skip(f"Trusted data file is not present: {path}")
    rows = 0
    max_value = None
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        columns = reader.fieldnames
        for row in reader:
            rows += 1
            value = row.get(date_column)
            if value and (max_value is None or value > max_value):
                max_value = value
    return columns, rows, max_value


def test_trusted_nswgov_csv_contract():
    columns, rows, max_fn_src = summarize_csv(REPO_ROOT / "data" / "nswgov_df.csv", "fn_src")

    assert columns == NSWGOV_COLUMNS
    assert rows >= 3_089_000
    assert max_fn_src >= "20260629.csv"


def test_trusted_rentboard_csv_contract():
    columns, rows, max_lodgement_dt = summarize_csv(REPO_ROOT / "data" / "rentboard_df.csv", "lodgement_dt")

    assert columns == RENTBOARD_COLUMNS
    assert rows >= 3_305_000
    assert max_lodgement_dt >= "2026-05-31"
