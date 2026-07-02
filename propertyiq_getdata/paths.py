from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class PipelinePaths:
    data_dir: Path

    @property
    def nswgov_final(self) -> Path:
        return self.data_dir / "nswgov_df.csv"

    @property
    def rentboard_final(self) -> Path:
        return self.data_dir / "rentboard_df.csv"

    def raw_source_dir(self, sourceid: str) -> Path:
        return self.data_dir / "raw" / sourceid

    def interim_source_dir(self, sourceid: str) -> Path:
        return self.data_dir / "interim" / sourceid

    def nswgov_etl2_dir(self) -> Path:
        return self.interim_source_dir("nswgov") / "output_etl2"

    def ensure_base_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.raw_source_dir("nswgov").mkdir(parents=True, exist_ok=True)
        self.raw_source_dir("rentboard").mkdir(parents=True, exist_ok=True)
        self.interim_source_dir("nswgov").mkdir(parents=True, exist_ok=True)
        self.interim_source_dir("rentboard").mkdir(parents=True, exist_ok=True)


def resolve_data_dir(data_dir: str | os.PathLike[str] | None = None) -> Path:
    """Resolve the canonical data directory.

    Precedence:
    1. Explicit CLI/function argument.
    2. PROPERTYIQ_DATA_DIR.
    3. DATA_DIR.
    4. Repo-local data/.
    """

    value = data_dir or os.environ.get("PROPERTYIQ_DATA_DIR") or os.environ.get("DATA_DIR")
    if value:
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = (REPO_ROOT / path).resolve()
        return path
    return REPO_ROOT / "data"


def get_paths(data_dir: str | os.PathLike[str] | None = None) -> PipelinePaths:
    return PipelinePaths(data_dir=resolve_data_dir(data_dir))
