"""What gets loaded: one ``LoadSpec`` per manifest dataset -> one ``raw`` table.

Naming rule (plan s03 §03): ``raw.<source>_<dataset>``. Source names appear
only here; from ``staging`` up, tables are named by domain.

Two load modes, decided by how the source partitions its output:

``partition``
    The file *is* the current truth for its slice (a week of sales, a month
    of bonds). A changed sha256 replaces that partition; a partition that
    disappears from the manifest is deleted from the table.
``snapshot``
    The file is one *vintage* of a revisable series (``asof=YYYY-MM-DD``).
    Vintages are appended and never deleted (decision D4), so ``staging``
    can expose both "latest" and "all".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ..sources.abs_ts import SERIES as ABS_TS_SERIES
from ..sources.rba import TABLES as RBA_TABLES

LoadMode = Literal["partition", "snapshot"]


@dataclass(frozen=True)
class LoadSpec:
    source: str
    dataset: str
    manifest: str  # attribute name on PipelinePaths
    mode: LoadMode

    @property
    def table(self) -> str:
        return raw_table_for(self.source, self.dataset)

    @property
    def key(self) -> str:
        """The ``--dataset`` selector: ``source/dataset``."""

        return f"{self.source}/{self.dataset}"


def raw_table_for(source: str, dataset: str) -> str:
    # rba datasets are already prefixed ``rba_`` by the source; don't double it.
    if dataset.startswith(f"{source}_"):
        return dataset
    return f"{source}_{dataset}"


LOAD_SPECS: tuple[LoadSpec, ...] = (
    LoadSpec("nswgov", "sales", "nswgov_manifest", "partition"),
    LoadSpec("rentboard", "lodgements", "rentboard_manifest", "partition"),
    *(LoadSpec("abs_ts", name, "abs_ts_manifest", "snapshot") for name in ABS_TS_SERIES),
    *(LoadSpec("rba", name, "rba_manifest", "snapshot") for name in RBA_TABLES),
)

LOAD_KEYS: tuple[str, ...] = tuple(spec.key for spec in LOAD_SPECS)


def select_specs(datasets: list[str] | None) -> list[LoadSpec]:
    """``--dataset`` accepts ``source/dataset`` keys or a bare source (all its datasets)."""

    if not datasets:
        return list(LOAD_SPECS)
    wanted: list[LoadSpec] = []
    for item in datasets:
        matches = [s for s in LOAD_SPECS if s.key == item or s.source == item]
        if not matches:
            raise ValueError(f"Unknown dataset {item!r}. Choices: {', '.join(LOAD_KEYS)}")
        wanted.extend(m for m in matches if m not in wanted)
    return wanted


__all__ = [
    "LOAD_KEYS",
    "LOAD_SPECS",
    "LoadMode",
    "LoadSpec",
    "raw_table_for",
    "select_specs",
]
