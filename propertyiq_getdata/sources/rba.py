"""RBA interest-rate tables (cash rate, lending rates, policy changes).

Interest rates are Reserve Bank data, not ABS. The RBA publishes each
statistical table as a static CSV at
``https://www.rba.gov.au/statistics/tables/csv/<table>-data.csv``, complete
history included (F5 back to 1959). Layout (verified 2026-09-21)::

    <title line, UTF-8 BOM>
    Title,<series title>,...
    Description,...
    Frequency,...
    Type,...
    Units,...
    <blank>
    Source,...
    Publication date,...
    Series ID,<id>,...            <- the stable column key
    DD/MM/YYYY,<v>,...            <- F1.1/F5 (end-of-month dates)
    DD-MMM-YYYY,<v>,...           <- A2 (as announced)
    <thousands of blank lines>

Columns are keyed by ``Series ID`` (titles get re-worded; IDs don't). The
default ``curl``/``requests`` User-Agent is refused, so a browser-like one is
sent. Same stages and snapshot contract as :mod:`sources.abs_ts`.
"""

from __future__ import annotations

import csv
import io
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

from ..core.manifest import write_multi_dataset_manifest
from ..core.paths import get_paths
from ..core.series import finalize_series_frame
from ..core.snapshot import (
    discover_snapshots,
    parse_asof,
    snapshot_path,
    snapshot_period_bounds,
    write_snapshot_if_changed,
)

SOURCE_ID = "rba"
SOURCE_URL = "https://www.rba.gov.au/statistics/tables/"
CSV_BASE = "https://www.rba.gov.au/statistics/tables/csv"


@dataclass(frozen=True)
class TableSpec:
    dataset: str
    table: str
    description: str


TABLES: dict[str, TableSpec] = {
    "rba_cash_rate": TableSpec(
        dataset="rba_cash_rate",
        table="f1.1",
        description="F1.1 Interest rates and yields, money market, monthly: cash rate target, interbank overnight, BABs, OIS",
    ),
    "rba_lending_rates": TableSpec(
        dataset="rba_lending_rates",
        table="f5",
        description="F5 Indicator lending rates, monthly: housing variable/fixed, owner-occupier vs investor, business, personal",
    ),
    "rba_rate_changes": TableSpec(
        dataset="rba_rate_changes",
        table="a2",
        description="A2 Changes in monetary policy: every cash rate target decision as announced, since 1990",
    ),
}

HEADER_ROWS = ("Title", "Description", "Frequency", "Type", "Units", "Source", "Publication date", "Series ID")
DATE_FORMATS = {
    re.compile(r"^\d{2}/\d{2}/\d{4}$"): "%d/%m/%Y",
    re.compile(r"^\d{2}-[A-Za-z]{3}-\d{4}$"): "%d-%b-%Y",
}
FREQ_CODES = {"monthly": "M", "daily": "D", "weekly": "W", "quarterly": "Q", "annual": "A"}
RAW_FILE_RE = re.compile(r"^asof=(?P<asof>\d{4}-\d{2}-\d{2})\.csv$")


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0 Safari/537.36"
            ),
            "Accept": "text/csv,*/*",
            "Referer": SOURCE_URL,
        }
    )
    return session


def rba_csv_url(table: str) -> str:
    return f"{CSV_BASE}/{table}-data.csv"


def raw_dataset_dir(data_dir: str | Path | None, dataset: str) -> Path:
    return get_paths(data_dir).raw_source_dir(SOURCE_ID) / dataset


def raw_file_path(data_dir: str | Path | None, dataset: str, asof: str) -> Path:
    return raw_dataset_dir(data_dir, dataset) / f"asof={asof}.csv"


def normalized_dataset_dir(data_dir: str | Path | None, dataset: str) -> Path:
    return get_paths(data_dir).rba_dir / dataset


def resolve_datasets(datasets: list[str] | tuple[str, ...] | None) -> list[TableSpec]:
    if not datasets:
        return list(TABLES.values())
    unknown = [name for name in datasets if name not in TABLES]
    if unknown:
        raise KeyError(f"Unknown rba dataset(s) {unknown}; known: {sorted(TABLES)}")
    return [TABLES[name] for name in datasets]


def fetch_rba_csv(session: requests.Session, table: str, *, retries: int = 3, timeout: int = 120) -> bytes:
    url = rba_csv_url(table)
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            response = session.get(url, timeout=timeout)
        except requests.RequestException as exc:
            last_error = exc
            time.sleep(2**attempt)
            continue
        if response.status_code >= 500:
            last_error = RuntimeError(f"HTTP {response.status_code} from {url}")
            time.sleep(2**attempt)
            continue
        response.raise_for_status()
        return response.content
    raise RuntimeError(f"Giving up on {url} after {retries} attempts: {last_error}")


def pull_rba(
    data_dir: str | Path | None = None,
    datasets: list[str] | tuple[str, ...] | None = None,
    asof: str | None = None,
    force: bool = False,
    dry_run: bool = False,
    session: requests.Session | None = None,
) -> pd.DataFrame:
    paths = get_paths(data_dir)
    paths.ensure_base_dirs()
    asof = parse_asof(asof)
    session = session or make_session()
    report = []
    for spec in resolve_datasets(datasets):
        target = raw_file_path(data_dir, spec.dataset, asof)
        url = rba_csv_url(spec.table)
        if target.exists() and not force:
            report.append({"dataset": spec.dataset, "table": spec.table, "url": url, "path": str(target), "status": "exists"})
            continue
        if dry_run:
            report.append({"dataset": spec.dataset, "table": spec.table, "url": url, "path": str(target), "status": "would-pull"})
            continue
        content = fetch_rba_csv(session, spec.table)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_bytes(content)
        tmp.replace(target)
        report.append({"dataset": spec.dataset, "table": spec.table, "url": url, "path": str(target), "status": "pulled"})
    return pd.DataFrame(report, columns=["dataset", "table", "url", "path", "status"])


def _parse_date(text: str) -> datetime | None:
    for pattern, fmt in DATE_FORMATS.items():
        if pattern.fullmatch(text):
            return datetime.strptime(text, fmt)
    return None


def _period_start(observed: datetime, freq: str) -> str:
    # Monthly tables are dated at month end (31/08/2026); the contract's join
    # key is the first day of the period. Event/daily rows keep their date.
    if freq == "M":
        return observed.replace(day=1).date().isoformat()
    return observed.date().isoformat()


def parse_rba_csv(path: str | Path, *, table: str | None = None) -> pd.DataFrame:
    """Melt one RBA table CSV to long form: one row per ``(date, series_id)``.

    Pure and offline. Cells that are non-empty but not numeric (A2's pre-1990
    ``"17.00 to 17.50"`` ranges) keep ``value`` NaN and the text in
    ``obs_comment``; empty cells are dropped.
    """

    text = Path(path).read_bytes().decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(text)))
    header: dict[str, list[str]] = {}
    data_rows: list[list[str]] = []
    for row in rows:
        if not row or not any(cell.strip() for cell in row):
            continue
        label = row[0].strip()
        if label in HEADER_ROWS:
            header[label] = [cell.strip() for cell in row[1:]]
        elif _parse_date(label) is not None:
            data_rows.append(row)
    if "Series ID" not in header:
        raise RuntimeError(f"{path} has no 'Series ID' row; RBA CSV layout changed")
    series_ids = header["Series ID"]
    if not data_rows:
        raise RuntimeError(f"ZERO rows in {path}; investigate")

    def col(name: str, index: int) -> str:
        values = header.get(name, [])
        return values[index] if index < len(values) else ""

    # A column whose Frequency reads "See notes" (F1.1 Treasury notes) takes
    # the table's dominant frequency; "As announced" (A2) is an event series.
    freq_by_column = [FREQ_CODES.get(col("Frequency", i).lower()) for i in range(len(series_ids))]
    known = [f for f in freq_by_column if f]
    default_freq = max(set(known), key=known.count) if known else "E"

    records = []
    for row in data_rows:
        observed = _parse_date(row[0].strip())
        assert observed is not None
        for index, series_id in enumerate(series_ids):
            cell = row[index + 1].strip() if index + 1 < len(row) else ""
            if not cell or not series_id:
                continue
            value = pd.to_numeric(cell, errors="coerce")
            freq = freq_by_column[index] or default_freq
            records.append(
                {
                    "series_id": series_id,
                    "series_label": col("Title", index),
                    "dataflow": table or "",
                    "freq": freq,
                    "time_period": row[0].strip(),
                    "period_start": _period_start(observed, freq),
                    "value": value,
                    "unit": col("Units", index),
                    "unit_mult": 0,
                    "obs_status": "",
                    "obs_comment": "" if pd.notna(value) else cell,
                    "region": "AUS",
                    "base_period": "",
                }
            )
    frame = pd.DataFrame(records)
    if frame.empty:
        raise RuntimeError(f"ZERO rows produced from {path}; investigate")
    return frame


def discover_raw(data_dir: str | Path | None, dataset: str) -> dict[str, Path]:
    found: dict[str, Path] = {}
    directory = raw_dataset_dir(data_dir, dataset)
    if not directory.exists():
        return found
    for path in directory.glob("asof=*.csv"):
        match = RAW_FILE_RE.fullmatch(path.name)
        if match:
            found[match.group("asof")] = path
    return found


def transform_rba(
    data_dir: str | Path | None = None,
    datasets: list[str] | tuple[str, ...] | None = None,
    asof: str | None = None,
) -> pd.DataFrame:
    paths = get_paths(data_dir)
    paths.ensure_base_dirs()
    report = []
    for spec in resolve_datasets(datasets):
        raw_by_asof = discover_raw(data_dir, spec.dataset)
        if not raw_by_asof:
            raise RuntimeError(f"No raw pull for rba/{spec.dataset}; run `rba pull` first.")
        use_asof = parse_asof(asof) if asof else max(raw_by_asof)
        if use_asof not in raw_by_asof:
            raise RuntimeError(f"rba/{spec.dataset} has no raw file for asof={use_asof}")
        frame = parse_rba_csv(raw_by_asof[use_asof], table=spec.table)
        frame = finalize_series_frame(frame, source=SOURCE_ID, dataset=spec.dataset, asof=use_asof)
        target = snapshot_path(normalized_dataset_dir(data_dir, spec.dataset), use_asof)
        written, status = write_snapshot_if_changed(frame, target)
        report.append(
            {
                "dataset": spec.dataset,
                "asof": use_asof,
                "path": str(written),
                "rows": int(frame.shape[0]),
                "period_start": str(frame["period_start"].min()),
                "period_end": str(frame["period_start"].max()),
                "status": status,
            }
        )
    refresh_rba_manifest(data_dir=data_dir)
    return pd.DataFrame(report, columns=["dataset", "asof", "path", "rows", "period_start", "period_end", "status"])


def discover_rba_partitions(data_dir: str | Path | None = None) -> dict[str, list[tuple[Path, str, str]]]:
    paths = get_paths(data_dir)
    partitions: dict[str, list[tuple[Path, str, str]]] = {}
    if not paths.rba_dir.exists():
        return partitions
    for dataset_dir in sorted(p for p in paths.rba_dir.iterdir() if p.is_dir()):
        for path, _asof in discover_snapshots(dataset_dir):
            start, end = snapshot_period_bounds(path)
            partitions.setdefault(dataset_dir.name, []).append((path, start, end))
    return partitions


def refresh_rba_manifest(data_dir: str | Path | None = None) -> pd.DataFrame:
    paths = get_paths(data_dir)
    return write_multi_dataset_manifest(
        data_dir=paths.data_dir,
        manifest_path=paths.rba_manifest,
        source=SOURCE_ID,
        partitions_by_dataset=discover_rba_partitions(data_dir),
    )


def update_rba(
    data_dir: str | Path | None = None,
    datasets: list[str] | tuple[str, ...] | None = None,
    asof: str | None = None,
    force: bool = False,
    dry_run: bool = False,
    session: requests.Session | None = None,
) -> pd.DataFrame:
    pulled = pull_rba(data_dir=data_dir, datasets=datasets, asof=asof, force=force, dry_run=dry_run, session=session)
    if dry_run:
        return pulled
    return transform_rba(data_dir=data_dir, datasets=datasets, asof=asof)
