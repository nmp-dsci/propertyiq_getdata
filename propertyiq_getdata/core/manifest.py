from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .io import atomic_write_csv


MANIFEST_COLUMNS = [
    "source",
    "dataset",
    "period_start",
    "period_end",
    "path",
    "rows",
    "sha256",
    "created_at_utc",
]


def file_sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def count_csv_rows(path: Path) -> int:
    with path.open("rb") as handle:
        return max(sum(1 for _ in handle) - 1, 0)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write_manifest(
    *,
    data_dir: Path,
    manifest_path: Path,
    source: str,
    dataset: str,
    partitions: list[tuple[Path, str, str]],
) -> pd.DataFrame:
    created_at = utc_now_iso()
    rows = []
    for path, period_start, period_end in sorted(partitions, key=lambda item: item[1]):
        rows.append(
            {
                "source": source,
                "dataset": dataset,
                "period_start": period_start,
                "period_end": period_end,
                "path": path.relative_to(data_dir).as_posix(),
                "rows": count_csv_rows(path),
                "sha256": file_sha256(path),
                "created_at_utc": created_at,
            }
        )
    manifest = pd.DataFrame(rows, columns=MANIFEST_COLUMNS)
    atomic_write_csv(manifest, manifest_path)
    return manifest
