import pandas as pd

from propertyiq_getdata.nswgov import (
    discover_links,
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


def test_transform_nswgov_appends_only_unprocessed_etl2_files(tmp_path):
    data_dir = tmp_path / "data"
    etl2_dir = data_dir / "interim" / "nswgov" / "output_etl2"
    etl2_dir.mkdir(parents=True)
    final_path = data_dir / "nswgov_df.csv"
    final_path.write_text(
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
    result = pd.read_csv(final_path, dtype=str)

    assert status["fn_src"].tolist() == ["20260105.csv"]
    assert result["fn_src"].tolist() == ["20250101.csv", "20260105.csv"]
    assert result.loc[result["fn_src"] == "20260105.csv", "sale_price"].iloc[0] == "2000000"
