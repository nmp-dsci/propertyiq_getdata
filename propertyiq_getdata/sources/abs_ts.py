"""ABS economic time series via the ABS Data API (SDMX 2.1 REST).

Not to be confused with ``sources/abs.py``, which is the 5-yearly Census
DataPack by postcode. This module collects the *time series* the ABS publishes
monthly/quarterly -- dwelling values and prices, CPI, labour force, wages,
housing lending, building approvals, population -- for every state and
territory plus Australia, with the full history the API holds.

Mechanics (verified live 2026-09-21):

* ``GET https://data.api.abs.gov.au/rest/data/ABS,{dataflow}/{key}`` with
  ``Accept: application/vnd.sdmx.data+csv;labels=both`` returns a tidy CSV whose
  dimension columns read ``"code: label"``. No auth.
* ``{key}`` is dot-separated dimension codes in DSD order; ``+`` ORs values and
  an empty position means "all". The number of positions must match the DSD
  exactly -- one short returns 404. REGION is always left empty (all states)
  and ``startPeriod`` is never sent (full history), both on purpose.
* A key that matches nothing answers **HTTP 404 with body ``NoRecordsFound``**;
  that is the zero-rows signal, raised per repo convention.

Stages: ``pull`` writes the API response verbatim to
``raw/abs_ts/<dataset>/asof=YYYY-MM-DD__<DATAFLOW>.csv``; ``transform`` parses
it into the shared long-format contract (:mod:`core.series`) and keeps a
``normalized/abs_ts/<dataset>/asof=YYYY-MM-DD.csv`` snapshot only when the
content differs from the newest one on disk (:mod:`core.snapshot`).
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import requests

from ..core.manifest import write_multi_dataset_manifest
from ..core.paths import get_paths
from ..core.series import DIM_PREFIX, finalize_series_frame, period_start, short_region
from ..core.snapshot import (
    discover_snapshots,
    parse_asof,
    snapshot_path,
    snapshot_period_bounds,
    write_snapshot_if_changed,
)

SOURCE_ID = "abs_ts"
SOURCE_URL = "https://www.abs.gov.au/statistics"
API_BASE = "https://data.api.abs.gov.au/rest"
CSV_ACCEPT = "application/vnd.sdmx.data+csv;labels=both"
NO_RECORDS = "NoRecordsFound"


@dataclass(frozen=True)
class SeriesSpec:
    """One dataset = one SDMX key applied to one or more dataflows.

    Several dataflows only where the ABS split a series across ASGS editions
    (building approvals); transform concatenates them and keeps ``dataflow``
    so the seam stays visible. There is deliberately no ``start_period`` and
    no region filter: every pull is the full history for every region.
    """

    dataset: str
    dataflows: tuple[str, ...]
    key: str
    description: str
    frozen: bool = False


SERIES: dict[str, SeriesSpec] = {
    "dwelling_values": SeriesSpec(
        dataset="dwelling_values",
        dataflows=("RES_DWELL_ST",),
        key="..Q",
        description="Total Value of Dwellings: value of stock, number of dwellings, mean price, by state",
    ),
    "dwelling_medians": SeriesSpec(
        dataset="dwelling_medians",
        dataflows=("RES_DWELL",),
        key="..Q",
        description="Total Value of Dwellings: median price and transfer counts, houses vs attached, by GCCSA",
    ),
    "cpi": SeriesSpec(
        dataset="cpi",
        dataflows=("CPI",),
        key="1+2+3.10001.10+20..Q+M",
        description="CPI all groups: index, % change q/q and y/y, original + seasonally adjusted, 8 capitals + AUS, quarterly and monthly",
    ),
    "labour_force": SeriesSpec(
        dataset="labour_force",
        dataflows=("LF",),
        key="M3+M6+M13+M16.3.1599.20+30..M",
        description="Labour force: employed, unemployed, unemployment rate, participation rate; persons, all ages; SA + trend; by state",
    ),
    "wpi": SeriesSpec(
        dataset="wpi",
        dataflows=("WPI",),
        key="1+3.THRPEB.7.TOT.10+20..Q",
        description="Wage Price Index: total hourly rates ex bonuses, all sectors/industries, original + SA, by state",
    ),
    "lending_housing": SeriesSpec(
        dataset="lending_housing",
        dataflows=("LEND_HOUSING",),
        key="FIN_NUM+FIN_VAL.NEWCOMMITS.DV8368.TOTDWELL+TOTHOUS.TOT.DV5167+DV5167_NONFHB+DV5168+DV5167_FHB+DV5168_FHB.20..Q",
        description="Lending indicators: new housing loan commitments (number, value), owner-occupier / investor / first home buyer, SA, by state",
    ),
    "building_approvals": SeriesSpec(
        dataset="building_approvals",
        dataflows=("BA_SA2_201116", "BA_SA2_2016-21", "BA_SA2"),
        key="1.9.1.100+110+120+130.STE+AUS..M",
        description="Building approvals: new dwelling units, total sectors, by building type, by state (three ASGS editions stitched)",
    ),
    "population": SeriesSpec(
        dataset="population",
        dataflows=("ERP_Q",),
        key="1+3.3.TOT..Q",
        description="Estimated resident population and annual % change, persons, all ages, by state",
    ),
}

# SDMX-CSV columns that are attributes, not dimensions. Everything else besides
# DATAFLOW / TIME_PERIOD / OBS_VALUE is treated as a dimension of the series.
ATTRIBUTE_COLUMNS = {"UNIT_MEASURE", "UNIT_MULT", "OBS_STATUS", "OBS_COMMENT", "DECIMALS", "BASE_PERIOD"}
DATAFLOW_RE = re.compile(r"^ABS:(?P<id>[^()]+)\((?P<version>[^)]+)\)$")
RAW_FILE_RE = re.compile(r"^asof=(?P<asof>\d{4}-\d{2}-\d{2})__(?P<dataflow>.+)\.csv$")


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "propertyiq-getdata/0.1 (+https://github.com/nmp-dsci/propertyiq_getdata)",
            "Accept": CSV_ACCEPT,
        }
    )
    return session


def sdmx_data_url(dataflow: str, key: str) -> str:
    return f"{API_BASE}/data/ABS,{dataflow}/{key}"


def raw_dataset_dir(data_dir: str | Path | None, dataset: str) -> Path:
    return get_paths(data_dir).raw_source_dir(SOURCE_ID) / dataset


def raw_file_path(data_dir: str | Path | None, dataset: str, asof: str, dataflow: str) -> Path:
    return raw_dataset_dir(data_dir, dataset) / f"asof={asof}__{dataflow}.csv"


def normalized_dataset_dir(data_dir: str | Path | None, dataset: str) -> Path:
    return get_paths(data_dir).abs_ts_dir / dataset


def resolve_datasets(datasets: list[str] | tuple[str, ...] | None) -> list[SeriesSpec]:
    if not datasets:
        return list(SERIES.values())
    unknown = [name for name in datasets if name not in SERIES]
    if unknown:
        raise KeyError(f"Unknown abs_ts dataset(s) {unknown}; known: {sorted(SERIES)}")
    return [SERIES[name] for name in datasets]


class NoRecordsError(RuntimeError):
    """The API answered NoRecordsFound: the key matches nothing (any more)."""


def fetch_sdmx_csv(
    session: requests.Session, dataflow: str, key: str, *, retries: int = 3, timeout: int = 300
) -> bytes:
    url = sdmx_data_url(dataflow, key)
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            response = session.get(url, timeout=timeout)
        except requests.RequestException as exc:  # connection reset, timeout, ...
            last_error = exc
            time.sleep(2**attempt)
            continue
        if response.status_code == 404 and NO_RECORDS in response.text:
            raise NoRecordsError(f"ZERO rows for {dataflow} key={key!r}; the API answered NoRecordsFound. investigate")
        if response.status_code >= 500:
            last_error = RuntimeError(f"HTTP {response.status_code} from {url}")
            time.sleep(2**attempt)
            continue
        response.raise_for_status()
        return response.content
    raise RuntimeError(f"Giving up on {url} after {retries} attempts: {last_error}")


def pull_abs_ts(
    data_dir: str | Path | None = None,
    datasets: list[str] | tuple[str, ...] | None = None,
    asof: str | None = None,
    force: bool = False,
    dry_run: bool = False,
    session: requests.Session | None = None,
) -> pd.DataFrame:
    """Download each registered dataflow verbatim into ``raw/abs_ts/<dataset>/``.

    Idempotent per ``(dataset, dataflow, asof)``: an existing raw file is kept
    unless ``force``. Raises on zero rows.
    """

    paths = get_paths(data_dir)
    paths.ensure_base_dirs()
    asof = parse_asof(asof)
    session = session or make_session()
    report = []
    for spec in resolve_datasets(datasets):
        for dataflow in spec.dataflows:
            target = raw_file_path(data_dir, spec.dataset, asof, dataflow)
            url = sdmx_data_url(dataflow, spec.key)
            if target.exists() and not force:
                report.append({"dataset": spec.dataset, "dataflow": dataflow, "url": url, "path": str(target), "status": "exists"})
                continue
            if dry_run:
                report.append({"dataset": spec.dataset, "dataflow": dataflow, "url": url, "path": str(target), "status": "would-pull"})
                continue
            content = fetch_sdmx_csv(session, dataflow, spec.key)
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_suffix(target.suffix + ".tmp")
            tmp.write_bytes(content)
            tmp.replace(target)
            report.append({"dataset": spec.dataset, "dataflow": dataflow, "url": url, "path": str(target), "status": "pulled"})
    return pd.DataFrame(report, columns=["dataset", "dataflow", "url", "path", "status"])


def _split_header(column: str) -> tuple[str, str]:
    """``"REGION: Region"`` -> ``("REGION", "Region")``; bare names pass through."""

    code, sep, label = column.partition(":")
    return (code.strip(), label.strip()) if sep else (column.strip(), column.strip())


def _split_cell(value: object) -> tuple[str, str]:
    """``"1: New South Wales"`` -> ``("1", "New South Wales")``; empty -> ``("", "")``."""

    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "", ""
    text = str(value)
    code, sep, label = text.partition(": ")
    return (code.strip(), label.strip()) if sep else (text.strip(), text.strip())


def parse_sdmx_csv(path: str | Path) -> pd.DataFrame:
    """Parse one SDMX-CSV (``labels=both``) response into contract columns + ``dim_*``.

    Pure and offline; the contract stamping (``source``/``dataset``/``asof``)
    and column ordering happen in :func:`finalize_series_frame`.
    """

    raw = pd.read_csv(path, dtype=str, keep_default_na=False)
    if raw.empty:
        raise RuntimeError(f"ZERO rows in {path}; investigate")
    columns = {name: _split_header(name)[0] for name in raw.columns}
    raw = raw.rename(columns=columns)
    required = {"DATAFLOW", "TIME_PERIOD", "OBS_VALUE"}
    if missing := required - set(raw.columns):
        raise RuntimeError(f"{path} is not SDMX-CSV: missing {sorted(missing)}")

    dims = [c for c in raw.columns if c not in required and c not in ATTRIBUTE_COLUMNS]
    out = pd.DataFrame(index=raw.index)

    flow = raw["DATAFLOW"].map(lambda v: DATAFLOW_RE.match(v).group("id") if DATAFLOW_RE.match(v) else v)
    out["dataflow"] = flow

    codes = {}
    labels = {}
    for dim in dims:
        split = raw[dim].map(_split_cell)
        codes[dim] = split.map(lambda pair: pair[0])
        labels[dim] = split.map(lambda pair: pair[1])
        out[f"{DIM_PREFIX}{dim}"] = codes[dim]
        out[f"{DIM_PREFIX}{dim}_label"] = labels[dim]

    key = pd.concat([codes[d] for d in dims], axis=1).agg(".".join, axis=1) if dims else pd.Series("", index=raw.index)
    out["series_id"] = flow + "." + key
    label_dims = [d for d in dims if d != "FREQ"]
    out["series_label"] = (
        pd.concat([labels[d] for d in label_dims], axis=1).agg(" · ".join, axis=1) if label_dims else ""
    )
    out["freq"] = codes.get("FREQ", "")
    out["time_period"] = raw["TIME_PERIOD"]
    out["period_start"] = [period_start(tp, f) for tp, f in zip(out["time_period"], out["freq"])]
    out["value"] = pd.to_numeric(raw["OBS_VALUE"], errors="coerce")

    def attr(name: str, which: int = 0) -> pd.Series:
        if name not in raw.columns:
            return pd.Series("", index=raw.index)
        return raw[name].map(lambda v: _split_cell(v)[which])

    out["unit"] = attr("UNIT_MEASURE")
    unit_mult = pd.to_numeric(attr("UNIT_MULT"), errors="coerce").fillna(0).astype(int)
    out["unit_mult"] = unit_mult
    out["obs_status"] = attr("OBS_STATUS")
    out["obs_comment"] = attr("OBS_COMMENT", 1)
    out["region"] = labels["REGION"].map(short_region) if "REGION" in labels else ""
    out["base_period"] = attr("BASE_PERIOD", 1)
    return out


def discover_raw(data_dir: str | Path | None, dataset: str) -> dict[str, dict[str, Path]]:
    """``{asof: {dataflow: path}}`` for every raw file of ``dataset``."""

    found: dict[str, dict[str, Path]] = {}
    directory = raw_dataset_dir(data_dir, dataset)
    if not directory.exists():
        return found
    for path in directory.glob("asof=*__*.csv"):
        match = RAW_FILE_RE.fullmatch(path.name)
        if match:
            found.setdefault(match.group("asof"), {})[match.group("dataflow")] = path
    return found


def transform_abs_ts(
    data_dir: str | Path | None = None,
    datasets: list[str] | tuple[str, ...] | None = None,
    asof: str | None = None,
) -> pd.DataFrame:
    """Parse the newest raw pull (or ``asof``) per dataset into a normalized snapshot."""

    paths = get_paths(data_dir)
    paths.ensure_base_dirs()
    report = []
    for spec in resolve_datasets(datasets):
        raw_by_asof = discover_raw(data_dir, spec.dataset)
        if not raw_by_asof:
            raise RuntimeError(f"No raw pull for abs_ts/{spec.dataset}; run `abs-ts pull` first.")
        use_asof = parse_asof(asof) if asof else max(raw_by_asof)
        files = raw_by_asof.get(use_asof, {})
        missing = [flow for flow in spec.dataflows if flow not in files]
        if missing:
            raise RuntimeError(f"abs_ts/{spec.dataset} asof={use_asof} is missing raw files for {missing}")
        frames = [parse_sdmx_csv(files[flow]) for flow in spec.dataflows]
        frame = finalize_series_frame(pd.concat(frames, ignore_index=True), source=SOURCE_ID, dataset=spec.dataset, asof=use_asof)
        if frame.empty:
            raise RuntimeError(f"ZERO rows produced for abs_ts/{spec.dataset}; investigate")
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
    refresh_abs_ts_manifest(data_dir=data_dir)
    return pd.DataFrame(report, columns=["dataset", "asof", "path", "rows", "period_start", "period_end", "status"])


def discover_abs_ts_partitions(data_dir: str | Path | None = None) -> dict[str, list[tuple[Path, str, str]]]:
    paths = get_paths(data_dir)
    partitions: dict[str, list[tuple[Path, str, str]]] = {}
    if not paths.abs_ts_dir.exists():
        return partitions
    for dataset_dir in sorted(p for p in paths.abs_ts_dir.iterdir() if p.is_dir()):
        for path, _asof in discover_snapshots(dataset_dir):
            start, end = snapshot_period_bounds(path)
            partitions.setdefault(dataset_dir.name, []).append((path, start, end))
    return partitions


def refresh_abs_ts_manifest(data_dir: str | Path | None = None) -> pd.DataFrame:
    """Rebuild ``abs_ts_manifest.csv`` from the snapshots on disk (one manifest, ``dataset`` column varies)."""

    paths = get_paths(data_dir)
    return write_multi_dataset_manifest(
        data_dir=paths.data_dir,
        manifest_path=paths.abs_ts_manifest,
        source=SOURCE_ID,
        partitions_by_dataset=discover_abs_ts_partitions(data_dir),
    )


def update_abs_ts(
    data_dir: str | Path | None = None,
    datasets: list[str] | tuple[str, ...] | None = None,
    asof: str | None = None,
    force: bool = False,
    dry_run: bool = False,
    session: requests.Session | None = None,
) -> pd.DataFrame:
    pulled = pull_abs_ts(data_dir=data_dir, datasets=datasets, asof=asof, force=force, dry_run=dry_run, session=session)
    if dry_run:
        return pulled
    return transform_abs_ts(data_dir=data_dir, datasets=datasets, asof=asof)
