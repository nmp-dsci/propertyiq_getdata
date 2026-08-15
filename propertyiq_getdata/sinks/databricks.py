"""Publish new or changed CSV partitions to a Databricks Unity Catalog volume as Parquet.

The publish is a stateless set difference. Every target file is named
``<partition>_<sha8>.parquet``, where ``sha8`` is the first eight hex characters
of that partition's sha256 as recorded in ``data/manifests/*.csv``. Because the
name encodes the content, diffing target names against the volume listing is
the same as diffing content -- there is no state file anywhere.

The landing area is append-only. A rewritten partition (rentboard rewrites its
trailing month on every run) uploads as a new file beside the old one; the
Databricks silver layer resolves which version wins. Nothing is ever
overwritten or deleted here.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from databricks.sdk.errors import AlreadyExists, NotFound, ResourceAlreadyExists

from ..core.paths import get_paths
from ..sources.nswgov import FINAL_COLUMNS as NSWGOV_COLUMNS
from ..sources.rentboard import FINAL_COLUMNS as RENTBOARD_COLUMNS

DEFAULT_VOLUME_ROOT = "/Volumes/workspace/propertyiq/propertyiq"

# Partition labels as they appear in the manifest 'path' column.
_SALES_PATH = re.compile(r"period=(?P<period>\d{8})\.csv$")
_LODGEMENTS_PATH = re.compile(r"year=(?P<year>\d{4})/month=(?P<month>\d{2})\.csv$")


@dataclass(frozen=True)
class DatasetSpec:
    """Everything that differs between the two datasets."""

    key: str
    source: str
    dataset: str
    columns: list[str]
    landing_dir: str
    manifest_attr: str


DATASETS: dict[str, DatasetSpec] = {
    "nswgov": DatasetSpec(
        key="nswgov",
        source="nswgov",
        dataset="sales",
        columns=list(NSWGOV_COLUMNS),
        landing_dir="sales",
        manifest_attr="nswgov_manifest",
    ),
    "rentboard": DatasetSpec(
        key="rentboard",
        source="rentboard",
        dataset="lodgements",
        columns=list(RENTBOARD_COLUMNS),
        landing_dir="lodgements",
        manifest_attr="rentboard_manifest",
    ),
}


class SchemaDriftError(RuntimeError):
    """A partition's columns no longer match its pinned FINAL_COLUMNS contract."""


@dataclass(frozen=True)
class PublishItem:
    """One partition that needs uploading."""

    dataset: str
    local_csv: Path
    remote_path: str
    name: str
    sha8: str
    period_start: str

    @property
    def columns(self) -> list[str]:
        return DATASETS[self.dataset].columns


@dataclass
class PublishReport:
    """What a publish run planned and did, per dataset and overall."""

    planned: list[PublishItem] = field(default_factory=list)
    uploaded: list[PublishItem] = field(default_factory=list)
    skipped: int = 0
    dry_run: bool = False

    def summary(self) -> str:
        return (
            f"planned {len(self.planned)}, "
            f"uploaded {len(self.uploaded)}, "
            f"skipped {self.skipped} already present"
        )


def target_name(dataset: str, path: str, sha256: str) -> str:
    """Build the content-addressed target filename for one manifest row.

    ``nswgov/sales/period=20260629.csv``            -> ``period=20260629_<sha8>.parquet``
    ``rentboard/lodgements/year=2026/month=06.csv`` -> ``month=2026-06_<sha8>.parquet``
    """

    sha8 = sha256.strip().lower()[:8]
    if len(sha8) < 8:
        raise ValueError(f"manifest sha256 too short for {path!r}: {sha256!r}")

    if dataset == "nswgov":
        match = _SALES_PATH.search(path)
        if not match:
            raise ValueError(f"unrecognised sales partition path: {path!r}")
        return f"period={match.group('period')}_{sha8}.parquet"

    if dataset == "rentboard":
        match = _LODGEMENTS_PATH.search(path)
        if not match:
            raise ValueError(f"unrecognised lodgements partition path: {path!r}")
        return f"month={match.group('year')}-{match.group('month')}_{sha8}.parquet"

    raise ValueError(f"unknown dataset: {dataset!r}")


def landing_dir(volume_root: str, dataset: str) -> str:
    return f"{volume_root.rstrip('/')}/landing/{DATASETS[dataset].landing_dir}"


def read_manifest(manifest_path: Path) -> pd.DataFrame:
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"manifest not found: {manifest_path}. Run the source's `manifest` "
            f"stage first so the sha256 per partition exists."
        )
    return pd.read_csv(manifest_path, dtype=str, keep_default_na=False)


def plan_publish(
    dataset: str,
    manifest: pd.DataFrame,
    existing_names: set[str],
    *,
    data_dir: Path,
    volume_root: str,
) -> list[PublishItem]:
    """Pure set difference: manifest-derived names minus what the volume already holds.

    Sorted oldest-first, so interrupting a long run always leaves a clean
    chronological prefix behind rather than a scattered subset.
    """

    remote_dir = landing_dir(volume_root, dataset)
    items: list[PublishItem] = []
    for row in manifest.to_dict("records"):
        name = target_name(dataset, row["path"], row["sha256"])
        if name in existing_names:
            continue
        items.append(
            PublishItem(
                dataset=dataset,
                local_csv=data_dir / row["path"],
                remote_path=f"{remote_dir}/{name}",
                name=name,
                sha8=row["sha256"][:8].lower(),
                period_start=row["period_start"],
            )
        )
    return sorted(items, key=lambda item: (item.period_start, item.name))


def csv_to_parquet(csv_path: Path, columns: list[str], out_path: Path) -> Path:
    """Convert one canonical CSV partition to all-string Parquet.

    Everything stays a string: the repo's output contract is all-string and the
    consumer types deliberately in one tested place. ``keep_default_na=False``
    is load-bearing -- it keeps ``""`` as an empty string rather than letting
    pandas turn it into NaN, which Parquet would store as NULL and silently
    change the consumer's empty-string semantics.
    """

    frame = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
    actual = list(frame.columns)
    if actual != columns:
        missing = [column for column in columns if column not in actual]
        extra = [column for column in actual if column not in columns]
        raise SchemaDriftError(
            f"{csv_path} does not match its FINAL_COLUMNS contract "
            f"(see tests/test_contract_outputs.py). "
            f"missing={missing or 'none'} extra={extra or 'none'} "
            f"order_changed={not missing and not extra}"
        )

    table = pa.Table.from_pandas(
        frame,
        schema=pa.schema([(column, pa.string()) for column in columns]),
        preserve_index=False,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = out_path.with_suffix(out_path.suffix + ".tmp")
    pq.write_table(table, tmp_path, compression="zstd")
    tmp_path.replace(out_path)
    return out_path


class Sink(Protocol):
    """The seam between planning (pure) and uploading (network)."""

    def list_names(self, directory: str) -> set[str]: ...

    def upload(self, local: Path, remote: str) -> None: ...


class VolumeSink:
    """The only thing in this module that talks to Databricks."""

    def __init__(self, profile: str = "DEFAULT") -> None:
        from databricks.sdk import WorkspaceClient

        self._client = WorkspaceClient(profile=profile)

    def list_names(self, directory: str) -> set[str]:
        """Names present in a volume directory; a missing directory is an empty set.

        On the very first run ``landing/`` does not exist yet -- upload creates
        parent directories implicitly, so "not found" simply means "publish
        everything".
        """

        try:
            return {entry.name for entry in self._client.files.list_directory_contents(directory)}
        except Exception as error:
            if _is_not_found(error):
                return set()
            raise

    def upload(self, local: Path, remote: str) -> None:
        """Upload one file, honouring the append-only contract.

        ``overwrite=False`` is the guard. If a previous run died after the
        server stored the bytes but before we recorded it, the retry gets an
        already-exists error; that is fine as long as the remote size matches,
        because the name is content-addressed. A size mismatch is a hard error.
        """

        with local.open("rb") as handle:
            try:
                self._client.files.upload(remote, handle, overwrite=False)
                return
            except Exception as error:
                if not _is_already_exists(error):
                    raise

        metadata = self._client.files.get_metadata(remote)
        remote_size = getattr(metadata, "content_length", None)
        local_size = local.stat().st_size
        if remote_size is not None and int(remote_size) != local_size:
            raise RuntimeError(
                f"{remote} already exists with {remote_size} bytes but the local "
                f"file is {local_size} bytes -- refusing to guess. Delete the "
                f"remote file and re-run to fix."
            )


def _is_not_found(error: Exception) -> bool:
    return isinstance(error, NotFound)


def _is_already_exists(error: Exception) -> bool:
    return isinstance(error, (AlreadyExists, ResourceAlreadyExists))


def publish_databricks(
    *,
    data_dir: str | Path | None = None,
    volume_root: str = DEFAULT_VOLUME_ROOT,
    profile: str = "DEFAULT",
    datasets: Iterable[str] = ("nswgov", "rentboard"),
    dry_run: bool = False,
    sink: Sink | None = None,
    workdir: Path | None = None,
    verbose: bool = True,
) -> PublishReport:
    """Convert and upload every partition the volume does not already hold.

    Idempotent by construction: run it twice and the second run uploads
    nothing. ``sink`` is injectable so tests never touch the network.
    """

    import tempfile

    paths = get_paths(data_dir)
    report = PublishReport(dry_run=dry_run)

    resolved_sink = sink
    if resolved_sink is None and not dry_run:
        resolved_sink = VolumeSink(profile=profile)

    for key in datasets:
        spec = DATASETS[key]
        manifest = read_manifest(getattr(paths, spec.manifest_attr))

        if resolved_sink is None:
            # A dry run with no sink still needs a listing to diff against; an
            # empty one shows the full bootstrap plan.
            existing: set[str] = _try_listing(profile, landing_dir(volume_root, key))
        else:
            existing = resolved_sink.list_names(landing_dir(volume_root, key))

        items = plan_publish(
            key,
            manifest,
            existing,
            data_dir=paths.data_dir,
            volume_root=volume_root,
        )
        report.planned.extend(items)
        report.skipped += len(manifest) - len(items)

        if dry_run:
            for item in items:
                if verbose:
                    print(f"[dry-run] would upload {item.local_csv.name} -> {item.remote_path}")
            continue

        assert resolved_sink is not None
        with tempfile.TemporaryDirectory(dir=workdir) as tmp:
            for item in items:
                local_parquet = Path(tmp) / item.name
                csv_to_parquet(item.local_csv, item.columns, local_parquet)
                resolved_sink.upload(local_parquet, item.remote_path)
                local_parquet.unlink(missing_ok=True)
                report.uploaded.append(item)
                if verbose:
                    print(f"uploaded {item.remote_path}")

    return report


def _try_listing(profile: str, directory: str) -> set[str]:
    """Best-effort listing for --dry-run; an unreachable workspace plans everything."""

    try:
        return VolumeSink(profile=profile).list_names(directory)
    except Exception as error:  # noqa: BLE001 - dry run must never fail on auth
        print(f"[dry-run] could not list {directory} ({error}); assuming empty")
        return set()
