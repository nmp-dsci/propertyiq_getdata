from __future__ import annotations

from pathlib import Path

import pandas as pd


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
