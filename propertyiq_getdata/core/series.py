"""The shared long-format contract for economic time series (abs_ts, rba).

One row per ``(series_id, time_period)``. The fixed ``CORE_COLUMNS`` are pinned
by the contract tests; a source may add any number of ``dim_*`` columns after
them (the SDMX dimensions of that dataflow), which are ragged across datasets
and deliberately not pinned.
"""

from __future__ import annotations

import re

import pandas as pd

CORE_COLUMNS = [
    "source",
    "dataset",
    "series_id",
    "series_label",
    "dataflow",
    "freq",
    "time_period",
    "period_start",
    "value",
    "unit",
    "unit_mult",
    "obs_status",
    "obs_comment",
    "region",
    "base_period",
    "asof",
]
DIM_PREFIX = "dim_"

# Publisher region labels -> the short form used in ``region`` so that the same
# place has the same key across dataflows. Anything not listed (capital cities,
# GCCSA rest-of-state areas) keeps its published label.
REGION_SHORT = {
    "Australia": "AUS",
    "Weighted average of eight capital cities": "AUS",
    "New South Wales": "NSW",
    "Victoria": "VIC",
    "Queensland": "QLD",
    "South Australia": "SA",
    "Western Australia": "WA",
    "Tasmania": "TAS",
    "Northern Territory": "NT",
    "Australian Capital Territory": "ACT",
}

_QUARTER = re.compile(r"^(\d{4})-Q([1-4])$")
_MONTH = re.compile(r"^(\d{4})-(\d{2})$")
_YEAR = re.compile(r"^(\d{4})$")
_FINANCIAL_YEAR = re.compile(r"^(\d{4})-(\d{2})$")
_DAY = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")


def period_start(time_period: str, freq: str | None = None) -> str:
    """ISO date of the first day of an SDMX ``TIME_PERIOD``.

    ``2026-Q2`` -> ``2026-04-01``; ``2026-07`` -> ``2026-07-01``; ``2026`` ->
    ``2026-01-01``; ``2026-07-15`` unchanged. A financial year such as
    ``2020-21`` is only recognised when ``freq`` says annual (``A``), because it
    is otherwise indistinguishable from a month.
    """

    value = str(time_period).strip()
    if match := _QUARTER.fullmatch(value):
        year, quarter = match.groups()
        return f"{year}-{(int(quarter) - 1) * 3 + 1:02d}-01"
    if match := _DAY.fullmatch(value):
        return value
    if freq == "A" and (match := _FINANCIAL_YEAR.fullmatch(value)) and int(match.group(2)) > 12:
        return f"{match.group(1)}-07-01"
    if match := _MONTH.fullmatch(value):
        return f"{match.group(1)}-{match.group(2)}-01"
    if match := _YEAR.fullmatch(value):
        return f"{value}-01-01"
    raise ValueError(f"Unrecognised TIME_PERIOD {time_period!r} (freq={freq!r})")


def short_region(label: str | None) -> str:
    if label is None or (isinstance(label, float) and pd.isna(label)):
        return ""
    return REGION_SHORT.get(str(label).strip(), str(label).strip())


def finalize_series_frame(frame: pd.DataFrame, *, source: str, dataset: str, asof: str) -> pd.DataFrame:
    """Stamp ``source``/``dataset``/``asof``, order columns, sort rows deterministically.

    Deterministic output matters: the snapshot dedupe compares file bytes.
    """

    frame = frame.copy()
    frame["source"] = source
    frame["dataset"] = dataset
    frame["asof"] = asof
    for column in CORE_COLUMNS:
        if column not in frame.columns:
            frame[column] = ""
    dims = sorted(column for column in frame.columns if column.startswith(DIM_PREFIX))
    extra = [c for c in frame.columns if c not in CORE_COLUMNS and c not in dims]
    if extra:
        raise ValueError(f"Non-contract columns in series frame: {extra}")
    frame = frame[CORE_COLUMNS + dims]
    frame = frame.sort_values(["series_id", "period_start", "dataflow"], kind="mergesort").reset_index(drop=True)
    return frame


__all__ = ["CORE_COLUMNS", "DIM_PREFIX", "REGION_SHORT", "finalize_series_frame", "period_start", "short_region"]
