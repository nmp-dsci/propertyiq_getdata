from __future__ import annotations

import zipfile
from pathlib import Path

import pandas as pd


def safe_extract_zip(zip_path: str | Path, extract_dir: str | Path) -> None:
    """Extract ``zip_path`` into ``extract_dir``, refusing zip-slip members."""

    zip_path = Path(zip_path)
    extract_dir = Path(extract_dir)
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zip_ref:
        for member in zip_ref.infolist():
            target = (extract_dir / member.filename).resolve()
            if not str(target).startswith(str(extract_dir.resolve())):
                raise ValueError(f"Refusing to extract unsafe zip member: {member.filename}")
        zip_ref.extractall(extract_dir)


def atomic_write_csv(frame: pd.DataFrame, path: str | Path, **to_csv_kwargs) -> Path:
    """Write ``frame`` to ``path`` atomically.

    The frame is written to a sibling ``*.tmp`` file first, then moved into
    place with :meth:`Path.replace`, so an interrupted run never leaves a
    half-written partition or manifest behind. Parent directories are created
    as needed. ``index=False`` is the default unless overridden.
    """

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    to_csv_kwargs.setdefault("index", False)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    frame.to_csv(tmp_path, **to_csv_kwargs)
    tmp_path.replace(path)
    return path
