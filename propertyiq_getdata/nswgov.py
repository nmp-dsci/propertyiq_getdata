from __future__ import annotations

import datetime as dt
import re
import zipfile
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup

from .paths import get_paths


SOURCE_URL = "https://valuation.property.nsw.gov.au/embed/propertySalesInformation"
SOURCE_ID = "nswgov"
FINAL_COLUMNS = [
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


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0 Safari/537.36"
            ),
            "Referer": SOURCE_URL,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
    )
    return session


def nswgov_dat_map() -> pd.DataFrame:
    rows = [
        {"record_type": "A", "variable": 0, "label": "record_type"},
        {"record_type": "A", "variable": 1, "label": "file_type"},
        {"record_type": "A", "variable": 2, "label": "district_code"},
        {"record_type": "A", "variable": 3, "label": "create_dt"},
        {"record_type": "A", "variable": 4, "label": "userid"},
        {"record_type": "B", "variable": 0, "label": "record_type"},
        {"record_type": "B", "variable": 1, "label": "district_code"},
        {"record_type": "B", "variable": 2, "label": "property_id"},
        {"record_type": "B", "variable": 3, "label": "sale_counter"},
        {"record_type": "B", "variable": 4, "label": "create_dt"},
        {"record_type": "B", "variable": 5, "label": "prop_name"},
        {"record_type": "B", "variable": 6, "label": "unit_no"},
        {"record_type": "B", "variable": 7, "label": "house_no"},
        {"record_type": "B", "variable": 8, "label": "street_name"},
        {"record_type": "B", "variable": 9, "label": "locality"},
        {"record_type": "B", "variable": 10, "label": "postcode"},
        {"record_type": "B", "variable": 11, "label": "area_sqm"},
        {"record_type": "B", "variable": 12, "label": "area_type"},
        {"record_type": "B", "variable": 13, "label": "contract_dt"},
        {"record_type": "B", "variable": 14, "label": "settle_dt"},
        {"record_type": "B", "variable": 15, "label": "sale_price"},
        {"record_type": "B", "variable": 16, "label": "zoning"},
        {"record_type": "B", "variable": 17, "label": "prop_nature"},
        {"record_type": "B", "variable": 18, "label": "prop_purpose"},
        {"record_type": "B", "variable": 19, "label": "strata_no"},
        {"record_type": "B", "variable": 20, "label": "component_cd"},
        {"record_type": "B", "variable": 21, "label": "sale_cd"},
        {"record_type": "B", "variable": 22, "label": "sale_interest"},
        {"record_type": "B", "variable": 23, "label": "dealing_no"},
        {"record_type": "C", "variable": 0, "label": "record_type"},
        {"record_type": "C", "variable": 1, "label": "district_code"},
        {"record_type": "C", "variable": 2, "label": "property_id"},
        {"record_type": "C", "variable": 3, "label": "sale_counter"},
        {"record_type": "C", "variable": 4, "label": "create_dt"},
        {"record_type": "C", "variable": 5, "label": "prop_desc"},
        {"record_type": "D", "variable": 0, "label": "record_type"},
        {"record_type": "D", "variable": 1, "label": "district_code"},
        {"record_type": "D", "variable": 2, "label": "property_id"},
        {"record_type": "D", "variable": 3, "label": "sale_counter"},
        {"record_type": "D", "variable": 4, "label": "create_dt"},
        {"record_type": "D", "variable": 5, "label": "vendor"},
        {"record_type": "Z", "variable": 0, "label": "record_type"},
        {"record_type": "Z", "variable": 1, "label": "total_records"},
        {"record_type": "Z", "variable": 2, "label": "records_b"},
        {"record_type": "Z", "variable": 3, "label": "records_c"},
        {"record_type": "Z", "variable": 4, "label": "records_d"},
    ]
    return pd.DataFrame(rows)


def discover_links(html: str) -> pd.DataFrame:
    soup = BeautifulSoup(html, "html.parser")
    records = []
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        if not href.lower().endswith(".zip"):
            continue
        parsed_path = urlparse(href).path.lower()
        filename = Path(parsed_path).stem
        if re.fullmatch(r"\d{8}", filename):
            term = "weekly"
        elif re.fullmatch(r"\d{4}", filename):
            term = "yearly"
        else:
            continue
        if "/weekly/" in parsed_path:
            term = "weekly"
        elif "/yearly/" in parsed_path or "/annual/" in parsed_path:
            term = "yearly"
        records.append({"term": term, "period": filename, "href": href})
    if not records:
        return pd.DataFrame(columns=["term", "period", "href"])
    return pd.DataFrame(records).drop_duplicates(["term", "period", "href"]).sort_values(["term", "period"])


def fetch_links(session: requests.Session | None = None) -> pd.DataFrame:
    session = session or make_session()
    html = session.get(SOURCE_URL, timeout=60).text
    return discover_links(html)


def latest_final_period(data_dir: str | Path | None = None) -> str | None:
    final_path = get_paths(data_dir).nswgov_final
    if not final_path.exists():
        return None
    final_df = pd.read_csv(final_path, usecols=["fn_src"], dtype=str)
    periods = final_df["fn_src"].dropna().str.extract(r"(\d{8})", expand=False).dropna()
    if periods.empty:
        return None
    return str(periods.max())


def filter_new_links(links: pd.DataFrame, latest_period: str | None) -> pd.DataFrame:
    if latest_period is None or links.empty:
        return links.copy()
    latest_year = latest_period[:4]
    keep = (
        ((links["term"] == "weekly") & (links["period"] > latest_period))
        | ((links["term"] == "yearly") & (links["period"] >= latest_year))
    )
    return links[keep].copy()


def _safe_extract(zip_path: Path, extract_dir: Path) -> None:
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zip_ref:
        for member in zip_ref.infolist():
            target = (extract_dir / member.filename).resolve()
            if not str(target).startswith(str(extract_dir.resolve())):
                raise ValueError(f"Refusing to extract unsafe zip member: {member.filename}")
        zip_ref.extractall(extract_dir)


def expand_nested_zips(root_dir: Path) -> pd.DataFrame:
    statuses = []
    for zip_path in sorted(root_dir.rglob("*.zip")):
        extract_dir = zip_path.with_suffix("")
        if extract_dir.exists() and any(extract_dir.rglob("*.DAT")):
            statuses.append({"zip_path": str(zip_path), "extract_dir": str(extract_dir), "status": "exists"})
            continue
        _safe_extract(zip_path, extract_dir)
        statuses.append({"zip_path": str(zip_path), "extract_dir": str(extract_dir), "status": "extracted"})
    return pd.DataFrame(statuses)


def pull_nswgov(
    data_dir: str | Path | None = None,
    terms: Iterable[str] = ("yearly", "weekly"),
    new_only: bool = True,
    dry_run: bool = False,
    session: requests.Session | None = None,
) -> pd.DataFrame:
    paths = get_paths(data_dir)
    paths.ensure_base_dirs()
    raw_dir = paths.raw_source_dir(SOURCE_ID)
    links = fetch_links(session=session)
    terms = set(terms)
    links = links[links["term"].isin(terms)].copy()
    if new_only:
        links = filter_new_links(links, latest_final_period(data_dir=data_dir))
    if links.empty:
        return pd.DataFrame(columns=["term", "period", "href", "path", "status"])

    statuses = []
    session = session or make_session()
    for record in links.to_dict(orient="records"):
        payload_dir = raw_dir / record["term"] / record["period"]
        complete = payload_dir.exists() and any(payload_dir.rglob("*.DAT"))
        status = "exists" if complete else "pending"
        if not complete and not dry_run:
            payload_dir.parent.mkdir(parents=True, exist_ok=True)
            zip_path = payload_dir.with_suffix(".zip")
            print(f"Downloading {record['term']} {record['period']}: {record['href']}")
            response = session.get(record["href"], timeout=120)
            response.raise_for_status()
            zip_path.write_bytes(response.content)
            _safe_extract(zip_path, payload_dir)
            zip_path.unlink()
            status = "downloaded"
        statuses.append({**record, "path": str(payload_dir), "status": status})
    return pd.DataFrame(statuses)


def normalise_ymd(value: str | Path) -> str | None:
    text = str(value)
    match = re.search(r"(\d{8})", text)
    if match:
        digits = match.group(1)
        yyyy = int(digits[:4])
        if 1900 <= yyyy <= 2100:
            return digits
        trailing_year = int(digits[4:])
        if 1900 <= trailing_year <= 2100:
            return dt.datetime.strptime(digits, "%d%m%Y").strftime("%Y%m%d")
        return digits
    match = re.search(r"([A-Za-z]+ \d{1,2}, \d{4})", text)
    if match:
        return dt.datetime.strptime(match.group(1).replace(" 0", " "), "%B %d, %Y").strftime("%Y%m%d")
    return None


def infer_dat_ymd(path: Path, fallback: str | None = None) -> str:
    for value in [*[part for part in reversed(path.parent.parts)], path.name]:
        parsed = normalise_ymd(value)
        if parsed:
            return parsed
    if fallback:
        return fallback
    raise ValueError(f"Could not infer YYYYMMDD period for {path}")


def parse_dat_file(dat_path: str | Path, ymd: str | None = None, mapping: pd.DataFrame | None = None) -> pd.DataFrame:
    dat_path = Path(dat_path)
    mapping = mapping if mapping is not None else nswgov_dat_map()
    with dat_path.open(encoding="latin1") as handle:
        raw_dat = pd.DataFrame({"raw": pd.Series(handle.readlines())})
    if raw_dat.empty:
        return pd.DataFrame(columns=["record_type", "index", "variable", "value", "label", "ymd", "file"])
    raw_dat = raw_dat["raw"].str.rstrip("\n\r").str.split(";", expand=True)
    raw_dat["record_type"] = raw_dat[0]
    raw_dat["index"] = raw_dat.index.values
    melted = raw_dat.melt(id_vars=["record_type", "index"])
    melted = melted.query("value == value").copy()
    melted = pd.merge(melted, mapping, on=["record_type", "variable"], how="left")
    melted["ymd"] = ymd or infer_dat_ymd(dat_path)
    melted["file"] = dat_path.name
    return melted


def extract_nswgov(data_dir: str | Path | None = None, new_only: bool = True) -> pd.DataFrame:
    paths = get_paths(data_dir)
    paths.ensure_base_dirs()
    raw_dir = paths.raw_source_dir(SOURCE_ID)
    export_dir = paths.nswgov_etl2_dir()
    export_dir.mkdir(parents=True, exist_ok=True)
    mapping = nswgov_dat_map()
    nested_status = expand_nested_zips(raw_dir)
    if not nested_status.empty:
        print(nested_status["status"].value_counts().to_string())
    dat_files = sorted((raw_dir).rglob("*.DAT"))
    if not dat_files:
        raise RuntimeError(f"No .DAT files found under {raw_dir}. Run nswgov pull first.")

    by_ymd: dict[str, list[Path]] = {}
    for dat_file in dat_files:
        ymd = infer_dat_ymd(dat_file)
        by_ymd.setdefault(ymd, []).append(dat_file)

    latest_period = latest_final_period(data_dir=data_dir) if new_only else None
    statuses = []
    for ymd, files in sorted(by_ymd.items()):
        if latest_period and ymd <= latest_period:
            statuses.append({"ymd": ymd, "files": len(files), "rows": None, "status": "trusted-final"})
            continue
        output_path = export_dir / f"{ymd}.csv"
        if output_path.exists():
            statuses.append({"ymd": ymd, "files": len(files), "rows": None, "status": "exists"})
            continue
        frames = [parse_dat_file(file_path, ymd=ymd, mapping=mapping) for file_path in files]
        file_extract = pd.concat(frames, axis=0, ignore_index=True) if frames else pd.DataFrame()
        print(f'saving file = "{ymd}" with {file_extract.shape[0]} rows')
        if file_extract.shape[0] == 0:
            raise RuntimeError(f"ZERO rows added for {ymd}; investigate source layout.")
        file_extract.to_csv(output_path, index=False)
        statuses.append({"ymd": ymd, "files": len(files), "rows": int(file_extract.shape[0]), "status": "written"})
    return pd.DataFrame(statuses)


def transform_etl2_frame(fn_df: pd.DataFrame, fn_src: str) -> pd.DataFrame:
    fn_df = fn_df.copy()
    fn_df["fn_src"] = fn_src
    fn_df = fn_df.query('record_type == "B"')
    fn_df = fn_df.query("label == label")
    fn_df["index"] = fn_df["index"].astype(str)
    if fn_df.empty:
        return pd.DataFrame(columns=FINAL_COLUMNS)
    wide = fn_df.groupby(["file", "fn_src", "ymd", "index", "label"])["value"].max().unstack("label")
    wide = wide.reset_index()
    for column in FINAL_COLUMNS:
        if column not in wide.columns:
            wide[column] = np.nan
    return wide[FINAL_COLUMNS]


def transform_nswgov(data_dir: str | Path | None = None) -> pd.DataFrame:
    paths = get_paths(data_dir)
    paths.ensure_base_dirs()
    input_dir = paths.nswgov_etl2_dir()
    output_path = paths.nswgov_final
    if not input_dir.exists():
        raise RuntimeError(f"Missing ETL2 directory {input_dir}; run nswgov extract first.")
    etl2_files = sorted(path for path in input_dir.glob("*.csv"))
    if not etl2_files:
        raise RuntimeError(f"No ETL2 CSV files found in {input_dir}.")

    if output_path.exists():
        print("EXISTING")
        processed = set(pd.read_csv(output_path, usecols=["fn_src"], dtype=str)["fn_src"].dropna().unique())
    else:
        print("NEW")
        processed = set()

    new_files = [path for path in etl2_files if path.name not in processed]
    first_write = not output_path.exists()
    for etl2_path in new_files:
        print(etl2_path.name)
        fn_df = pd.read_csv(etl2_path, dtype=str)
        fn_df2 = transform_etl2_frame(fn_df, fn_src=etl2_path.name)
        print(f'saving file = "{etl2_path.name}" with {fn_df2.shape[0]} rows')
        if fn_df2.shape[0] == 0:
            raise RuntimeError(f"ZERO rows added for {etl2_path.name}; investigate source layout.")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fn_df2.to_csv(output_path, mode="w" if first_write else "a", header=first_write, index=False)
        first_write = False

    print(f"saving file = {output_path}")
    return pd.DataFrame({"fn_src": [path.name for path in new_files], "status": "added"})


def update_nswgov(data_dir: str | Path | None = None, dry_run: bool = False, new_only: bool = True) -> None:
    pull_nswgov(data_dir=data_dir, dry_run=dry_run, new_only=new_only)
    if dry_run:
        return
    extract_nswgov(data_dir=data_dir, new_only=new_only)
    transform_nswgov(data_dir=data_dir)
