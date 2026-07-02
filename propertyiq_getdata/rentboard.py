from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup

from .paths import get_paths


SOURCE_ID = "rentboard"
SOURCE_URL = "https://www.nsw.gov.au/housing-and-construction/rental-forms-surveys-and-data/rental-bond-data"
SITE_ROOT = "https://www.nsw.gov.au"
XLSX_COLUMNS = ["Lodgement Date", "Postcode", "Dwelling Type", "Bedrooms", "Weekly Rent"]
FINAL_COLUMNS = ["lodgement_dt", "postcode", "property_type", "bedrooms", "weekly_rent"]
MONTH_PATTERN = re.compile(
    r"(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{4})",
    flags=re.IGNORECASE,
)


def discover_links(html: str) -> pd.DataFrame:
    soup = BeautifulSoup(html, "html.parser")
    records = []
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        if not href.lower().endswith(".xlsx"):
            continue
        title = anchor.get("title") or anchor.get_text(" ", strip=True) or Path(href).stem
        title_clean = re.sub(r"\s+", " ", title).strip()
        title_lower = title_clean.lower()
        if any(skip in title_lower for skip in ["copy", "refund", "bonds held", "readspeaker"]):
            continue

        year_match = re.search(r"(?:year|for year)\s+(\d{4})\b", title_clean, flags=re.IGNORECASE)
        month_match = MONTH_PATTERN.search(title_clean.replace("-", " "))
        if year_match:
            period = "annual"
            period_value = year_match.group(1)
            period_start = pd.Timestamp(f"{period_value}-01-01")
        elif month_match:
            period = "month"
            period_value = f"{month_match.group(1).title()} {month_match.group(2)}"
            period_start = pd.to_datetime(period_value, format="%B %Y")
        else:
            continue

        records.append(
            {
                "href": urljoin(SITE_ROOT, href),
                "title": title_clean,
                "period": period,
                "period_value": period_value,
                "period_start": period_start,
            }
        )
    if not records:
        return pd.DataFrame(columns=["href", "title", "period", "period_value", "period_start"])
    return (
        pd.DataFrame(records)
        .drop_duplicates(["href", "period", "period_value"])
        .sort_values(["period_start", "href"])
        .reset_index(drop=True)
    )


def fetch_links(session: requests.Session | None = None) -> pd.DataFrame:
    session = session or requests.Session()
    html = session.get(SOURCE_URL, timeout=60).text
    return discover_links(html)


def normalize_rentboard_frame(df: pd.DataFrame) -> pd.DataFrame:
    missing = [column for column in XLSX_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"Missing expected rentboard columns: {missing}")
    out = df[XLSX_COLUMNS].copy()
    out = out.rename(
        columns={
            "Lodgement Date": "lodgement_dt",
            "Postcode": "postcode",
            "Dwelling Type": "property_type",
            "Bedrooms": "bedrooms",
            "Weekly Rent": "weekly_rent",
        }
    )
    out = out.dropna(how="all")
    out["lodgement_dt"] = pd.to_datetime(out["lodgement_dt"], errors="coerce")
    out = out[out["lodgement_dt"].notna()].copy()
    out["lodgement_dt"] = out["lodgement_dt"].dt.strftime("%Y-%m-%d")
    return out[FINAL_COLUMNS]


def xlsx_to_normalized_csv(xlsx_path: str | Path, csv_path: str | Path | None = None) -> pd.DataFrame:
    xlsx_path = Path(xlsx_path)
    df = pd.read_excel(xlsx_path, header=2)
    normalized = normalize_rentboard_frame(df)
    if csv_path is not None:
        Path(csv_path).parent.mkdir(parents=True, exist_ok=True)
        normalized.to_csv(csv_path, index=False)
    return normalized


def prefer_monthly_when_available(links: pd.DataFrame) -> pd.DataFrame:
    if links.empty:
        return links.copy()
    selected = links.copy()
    selected["year"] = pd.to_datetime(selected["period_start"]).dt.year
    monthly_years = set(selected.loc[selected["period"] == "month", "year"])
    selected = selected[(selected["period"] != "annual") | (~selected["year"].isin(monthly_years))].copy()
    return selected.drop(columns=["year"])


def update_rentboard(
    data_dir: str | Path | None = None,
    dry_run: bool = False,
    session: requests.Session | None = None,
) -> pd.DataFrame:
    paths = get_paths(data_dir)
    paths.ensure_base_dirs()
    raw_dir = paths.raw_source_dir(SOURCE_ID)
    raw_xlsx_dir = raw_dir / "xlsx"
    raw_csv_dir = raw_dir / "csv"
    raw_xlsx_dir.mkdir(parents=True, exist_ok=True)
    raw_csv_dir.mkdir(parents=True, exist_ok=True)

    links = fetch_links(session=session)
    if links.empty:
        raise RuntimeError("No rentboard XLSX links discovered; source page may have changed.")

    final_path = paths.rentboard_final
    if final_path.exists():
        existing = pd.read_csv(final_path, dtype=str)
        existing_max_dt = pd.to_datetime(existing["lodgement_dt"], errors="coerce").max()
    else:
        existing = pd.DataFrame(columns=FINAL_COLUMNS)
        existing_max_dt = pd.Timestamp.min

    selected = links[links["period_start"] >= existing_max_dt.replace(day=1)].copy()
    selected = prefer_monthly_when_available(selected)
    statuses = []
    new_frames = []
    session = session or requests.Session()
    for record in selected.to_dict(orient="records"):
        slug = re.sub(r"[^A-Za-z0-9]+", "_", record["period_value"]).strip("_").lower()
        file_id = f"{record['period']}_{slug}"
        xlsx_path = raw_xlsx_dir / f"{file_id}.xlsx"
        csv_path = raw_csv_dir / f"{file_id}.csv"
        if dry_run:
            statuses.append({**record, "status": "pending", "xlsx_path": str(xlsx_path), "csv_path": str(csv_path)})
            continue

        if not xlsx_path.exists():
            print(f"Downloading rentboard {record['period_value']}: {record['href']}")
            response = session.get(record["href"], timeout=120)
            response.raise_for_status()
            xlsx_path.write_bytes(response.content)
        normalized = xlsx_to_normalized_csv(xlsx_path, csv_path=csv_path)
        normalized_dt = pd.to_datetime(normalized["lodgement_dt"], errors="coerce")
        normalized = normalized[normalized_dt > existing_max_dt].copy()
        if not normalized.empty:
            new_frames.append(normalized)
        statuses.append(
            {
                **record,
                "status": "processed",
                "xlsx_path": str(xlsx_path),
                "csv_path": str(csv_path),
                "new_rows": int(normalized.shape[0]),
            }
        )

    if not dry_run:
        if new_frames:
            new_df = pd.concat(new_frames, axis=0, ignore_index=True)
            rent_df = pd.concat([existing, new_df], axis=0, ignore_index=True)
        else:
            rent_df = existing
        final_path.parent.mkdir(parents=True, exist_ok=True)
        rent_df[FINAL_COLUMNS].to_csv(final_path, index=False)
        print(f"saving file = {rent_df.shape[0]} rows")

    return pd.DataFrame(statuses)
