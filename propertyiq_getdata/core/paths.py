from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


# This file lives at <repo>/propertyiq_getdata/core/paths.py, so the repo root
# is three levels up.
REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class PipelinePaths:
    data_dir: Path

    @property
    def nswgov_final(self) -> Path:
        return self.data_dir / "nswgov_df.csv"

    @property
    def rentboard_final(self) -> Path:
        return self.data_dir / "rentboard_df.csv"

    @property
    def manifests_dir(self) -> Path:
        return self.data_dir / "manifests"

    @property
    def nswgov_sales_dir(self) -> Path:
        return self.data_dir / "normalized" / "nswgov" / "sales"

    @property
    def rentboard_lodgements_dir(self) -> Path:
        return self.data_dir / "normalized" / "rentboard" / "lodgements"

    @property
    def abs_poa_dir(self) -> Path:
        return self.data_dir / "normalized" / "abs" / "poa"

    @property
    def nswgov_manifest(self) -> Path:
        return self.manifests_dir / "nswgov_sales_manifest.csv"

    @property
    def rentboard_manifest(self) -> Path:
        return self.manifests_dir / "rentboard_lodgements_manifest.csv"

    @property
    def abs_poa_manifest(self) -> Path:
        return self.manifests_dir / "abs_poa_manifest.csv"

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
        self.raw_source_dir("abs").mkdir(parents=True, exist_ok=True)
        self.interim_source_dir("nswgov").mkdir(parents=True, exist_ok=True)
        self.interim_source_dir("rentboard").mkdir(parents=True, exist_ok=True)
        self.interim_source_dir("abs").mkdir(parents=True, exist_ok=True)
        self.manifests_dir.mkdir(parents=True, exist_ok=True)
        self.nswgov_sales_dir.mkdir(parents=True, exist_ok=True)
        self.rentboard_lodgements_dir.mkdir(parents=True, exist_ok=True)
        self.abs_poa_dir.mkdir(parents=True, exist_ok=True)


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
