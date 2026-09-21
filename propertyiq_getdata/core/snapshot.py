"""Snapshot-per-release partitions for revisable time series.

Publishers such as the ABS and RBA revise history (seasonal re-estimation,
``p`` -> ``r`` flags, index rebases), so a partition keyed on the observation
period would silently go stale. Instead each run captures the full series as
the publisher currently states it, keyed on the capture date::

    normalized/<source>/<dataset>/asof=YYYY-MM-DD.csv

and keeps the new snapshot only when its content differs from the newest one
already on disk. A weekly cron therefore produces a new file only when the
publisher actually released something.
"""

from __future__ import annotations

import hashlib
import re
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

from .io import atomic_write_csv

ASOF_RE = re.compile(r"^asof=(?P<asof>\d{4}-\d{2}-\d{2})\.csv$")


def today_asof() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def parse_asof(value: str | date | None) -> str:
    """Normalise an ``--asof`` argument to ``YYYY-MM-DD``; ``None`` means today."""

    if value is None:
        return today_asof()
    if isinstance(value, date):
        return value.isoformat()
    return date.fromisoformat(str(value)).isoformat()


def snapshot_path(directory: Path, asof: str) -> Path:
    return directory / f"asof={asof}.csv"


def discover_snapshots(directory: Path) -> list[tuple[Path, str]]:
    """Every ``asof=*.csv`` under ``directory``, oldest first."""

    found = []
    if not directory.exists():
        return found
    for path in directory.glob("asof=*.csv"):
        match = ASOF_RE.fullmatch(path.name)
        if match:
            found.append((path, match.group("asof")))
    return sorted(found, key=lambda item: item[1])


def latest_snapshot(directory: Path) -> Path | None:
    snapshots = discover_snapshots(directory)
    return snapshots[-1][0] if snapshots else None


VINTAGE_COLUMNS = ("asof",)


def content_digest(path: Path, ignore: tuple[str, ...] = VINTAGE_COLUMNS) -> str:
    """sha256 of a snapshot's *content* -- every column except the vintage stamp.

    The ``asof`` column differs between two otherwise identical releases, so
    a plain file hash would never match across days. Both sides of every
    comparison go through this same read/serialise path, so the digest is
    stable even where CSV round-tripping is not byte-exact.
    """

    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    frame = frame.drop(columns=[c for c in ignore if c in frame.columns])
    return hashlib.sha256(frame.to_csv(index=False).encode("utf-8")).hexdigest()


def write_snapshot_if_changed(frame: pd.DataFrame, path: Path) -> tuple[Path, str]:
    """Write ``frame`` to ``path`` unless the newest sibling snapshot has the same content.

    Content is compared ignoring the ``asof`` vintage column (see
    :func:`content_digest`). Returns ``(path, status)`` where status is
    ``"written"``, ``"unchanged"`` (the newest existing snapshot has the same
    content; nothing written) or ``"rewritten"`` (``path`` itself already
    existed and was replaced -- a same-day rerun after a fix).
    """

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    frame.to_csv(tmp_path, index=False)

    existed = path.exists()
    # Compare against the newest snapshot on disk -- which is ``path`` itself on
    # a same-day rerun, or the previous release otherwise.
    previous = path if existed else latest_snapshot(path.parent)
    if previous is not None and content_digest(previous) == content_digest(tmp_path):
        tmp_path.unlink()
        return previous, "unchanged"
    tmp_path.replace(path)
    return path, "rewritten" if existed else "written"


def snapshot_period_bounds(path: Path, column: str = "period_start") -> tuple[str, str]:
    """``(min, max)`` of ``column`` in a snapshot, for the manifest."""

    values = pd.read_csv(path, usecols=[column], dtype=str)[column].dropna()
    if values.empty:
        return "", ""
    return str(values.min()), str(values.max())


__all__ = [
    "ASOF_RE",
    "VINTAGE_COLUMNS",
    "atomic_write_csv",
    "content_digest",
    "discover_snapshots",
    "latest_snapshot",
    "parse_asof",
    "snapshot_path",
    "snapshot_period_bounds",
    "today_asof",
    "write_snapshot_if_changed",
]
