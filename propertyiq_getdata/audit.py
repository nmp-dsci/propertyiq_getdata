from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from .paths import get_paths


def file_sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def audit_outputs(data_dir: str | Path | None = None) -> dict[str, Any]:
    paths = get_paths(data_dir)
    return {
        "data_dir": str(paths.data_dir),
        "nswgov": csv_summary(paths.nswgov_final, date_column="fn_src"),
        "rentboard": csv_summary(paths.rentboard_final, date_column="lodgement_dt"),
    }


def print_audit(data_dir: str | Path | None = None) -> None:
    print(json.dumps(audit_outputs(data_dir=data_dir), indent=2))
