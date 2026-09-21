from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import pandas as pd

from .core.manifest import file_sha256
from .core.paths import get_paths


def csv_summary(path: Path, date_column: str | None = None) -> dict[str, Any]:
    if not path.exists():
        return {"path": str(path), "exists": False}
    rows = 0
    max_value = None
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        columns = reader.fieldnames or []
        for row in reader:
            rows += 1
            if date_column:
                value = row.get(date_column)
                if value and (max_value is None or value > max_value):
                    max_value = value
    summary = {
        "path": str(path),
        "exists": True,
        "rows": rows,
        "columns": columns,
        "sha256": file_sha256(path),
    }
    if date_column:
        summary[f"max_{date_column}"] = max_value
    return summary


def manifest_summary(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": str(path), "exists": False}
    manifest = pd.read_csv(path, dtype=str)
    summary = {
        "path": str(path),
        "exists": True,
        "partitions": int(manifest.shape[0]),
        "columns": list(manifest.columns),
        "sha256": file_sha256(path),
    }
    if "period_end" in manifest.columns and not manifest.empty:
        summary["max_period_end"] = manifest["period_end"].max()
    if "rows" in manifest.columns and not manifest.empty:
        summary["rows"] = int(pd.to_numeric(manifest["rows"], errors="coerce").fillna(0).sum())
    return summary


def snapshot_summary(manifest_path: Path) -> dict[str, dict[str, Any]]:
    """Per-dataset view of a snapshot manifest: newest asof, its rows and period span."""

    if not manifest_path.exists():
        return {}
    manifest = pd.read_csv(manifest_path, dtype=str)
    if manifest.empty:
        return {}
    manifest["asof"] = manifest["path"].str.extract(r"asof=(\d{4}-\d{2}-\d{2})\.csv$")[0]
    summary: dict[str, dict[str, Any]] = {}
    for dataset, group in manifest.groupby("dataset"):
        newest = group.sort_values("asof").iloc[-1]
        summary[str(dataset)] = {
            "snapshots": int(group.shape[0]),
            "latest_asof": newest["asof"],
            "rows": int(newest["rows"]),
            "period_start": newest["period_start"],
            "period_end": newest["period_end"],
        }
    return summary


def audit_outputs(data_dir: str | Path | None = None) -> dict[str, Any]:
    paths = get_paths(data_dir)
    return {
        "data_dir": str(paths.data_dir),
        "nswgov": {
            "manifest": manifest_summary(paths.nswgov_manifest),
            "legacy_csv": csv_summary(paths.nswgov_final, date_column="fn_src"),
        },
        "rentboard": {
            "manifest": manifest_summary(paths.rentboard_manifest),
            "legacy_csv": csv_summary(paths.rentboard_final, date_column="lodgement_dt"),
        },
        "abs": {
            "manifest": manifest_summary(paths.abs_poa_manifest),
        },
        "abs_ts": {
            "manifest": manifest_summary(paths.abs_ts_manifest),
            "datasets": snapshot_summary(paths.abs_ts_manifest),
        },
        "rba": {
            "manifest": manifest_summary(paths.rba_manifest),
            "datasets": snapshot_summary(paths.rba_manifest),
        },
    }


def print_audit(data_dir: str | Path | None = None) -> None:
    print(json.dumps(audit_outputs(data_dir=data_dir), indent=2))
