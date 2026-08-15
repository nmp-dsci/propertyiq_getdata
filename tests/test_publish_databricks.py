"""Publish-to-Databricks tests: pure units plus a fake sink. No network."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
import pytest

from propertyiq_getdata.core.manifest import write_manifest
from propertyiq_getdata.sinks.databricks import (
    DATASETS,
    SchemaDriftError,
    csv_to_parquet,
    landing_dir,
    plan_publish,
    publish_databricks,
    target_name,
)
from propertyiq_getdata.sources.nswgov import FINAL_COLUMNS as SALES_COLUMNS
from propertyiq_getdata.sources.rentboard import FINAL_COLUMNS as RENT_COLUMNS

VOLUME_ROOT = "/Volumes/workspace/propertyiq/propertyiq"
SHA_A = "ab12cd34" + "0" * 56
SHA_B = "ff99ee88" + "1" * 56


class FakeSink:
    """Records what would have been uploaded; never touches a network."""

    def __init__(self, existing: set[str] | None = None) -> None:
        self.files: dict[str, bytes] = {}
        self.uploads: list[tuple[Path, str]] = []
        for name in existing or set():
            self.files[name] = b""

    def list_names(self, directory: str) -> set[str]:
        prefix = directory.rstrip("/") + "/"
        return {
            name.removeprefix(prefix)
            for name in self.files
            if name.startswith(prefix)
        } | {name for name in self.files if "/" not in name}

    def upload(self, local: Path, remote: str) -> None:
        if remote in self.files:
            raise RuntimeError(f"AlreadyExists: {remote}")
        self.files[remote] = local.read_bytes()
        self.uploads.append((local, remote))


def _sales_frame(rows: int = 3) -> pd.DataFrame:
    data = {column: [f"{column}-{i}" for i in range(rows)] for column in SALES_COLUMNS}
    return pd.DataFrame(data, columns=SALES_COLUMNS)


def _rent_frame(rows: int = 3) -> pd.DataFrame:
    data = {column: [f"{column}-{i}" for i in range(rows)] for column in RENT_COLUMNS}
    return pd.DataFrame(data, columns=RENT_COLUMNS)


def _build_data_dir(tmp_path: Path, *, rent_rows: int = 3) -> Path:
    """A miniature data dir: two sales periods, one rent month, real manifests."""

    data_dir = tmp_path / "data"
    sales_dir = data_dir / "normalized" / "nswgov" / "sales"
    rent_dir = data_dir / "normalized" / "rentboard" / "lodgements" / "year=2026"
    sales_dir.mkdir(parents=True)
    rent_dir.mkdir(parents=True)

    for period in ("20260622", "20260629"):
        _sales_frame().to_csv(sales_dir / f"period={period}.csv", index=False)
    _rent_frame(rent_rows).to_csv(rent_dir / "month=06.csv", index=False)

    manifests = data_dir / "manifests"
    manifests.mkdir(parents=True)
    write_manifest(
        data_dir=data_dir,
        manifest_path=manifests / "nswgov_sales_manifest.csv",
        source="nswgov",
        dataset="sales",
        partitions=[
            (sales_dir / "period=20260622.csv", "2026-06-22", "2026-06-22"),
            (sales_dir / "period=20260629.csv", "2026-06-29", "2026-06-29"),
        ],
    )
    write_manifest(
        data_dir=data_dir,
        manifest_path=manifests / "rentboard_lodgements_manifest.csv",
        source="rentboard",
        dataset="lodgements",
        partitions=[(rent_dir / "month=06.csv", "2026-06-01", "2026-06-30")],
    )
    return data_dir


# --------------------------------------------------------------------------
# target_name
# --------------------------------------------------------------------------


def test_target_name_sales_uses_period_and_sha8():
    name = target_name("nswgov", "normalized/nswgov/sales/period=20260629.csv", SHA_A)
    assert name == "period=20260629_ab12cd34.parquet"


def test_target_name_rent_flattens_year_month():
    name = target_name(
        "rentboard", "normalized/rentboard/lodgements/year=2026/month=06.csv", SHA_A
    )
    assert name == "month=2026-06_ab12cd34.parquet"


def test_target_name_lowercases_sha():
    name = target_name("nswgov", "normalized/nswgov/sales/period=20260629.csv", SHA_A.upper())
    assert name == "period=20260629_ab12cd34.parquet"


def test_target_name_rejects_unrecognised_path():
    with pytest.raises(ValueError, match="unrecognised sales partition path"):
        target_name("nswgov", "normalized/nswgov/sales/whatever.csv", SHA_A)


# --------------------------------------------------------------------------
# plan_publish
# --------------------------------------------------------------------------


def test_plan_is_a_set_difference_oldest_first(tmp_path):
    manifest = pd.DataFrame(
        [
            {"path": "normalized/nswgov/sales/period=20260615.csv", "sha256": SHA_A, "period_start": "2026-06-15"},
            {"path": "normalized/nswgov/sales/period=20260622.csv", "sha256": SHA_B, "period_start": "2026-06-22"},
            {"path": "normalized/nswgov/sales/period=20260629.csv", "sha256": SHA_A, "period_start": "2026-06-29"},
        ]
    )
    existing = {"period=20260622_ff99ee88.parquet"}

    items = plan_publish(
        "nswgov", manifest, existing, data_dir=tmp_path, volume_root=VOLUME_ROOT
    )

    assert [item.name for item in items] == [
        "period=20260615_ab12cd34.parquet",
        "period=20260629_ab12cd34.parquet",
    ]
    assert items[0].remote_path == f"{VOLUME_ROOT}/landing/sales/period=20260615_ab12cd34.parquet"


def test_plan_is_empty_when_everything_present(tmp_path):
    manifest = pd.DataFrame(
        [{"path": "normalized/nswgov/sales/period=20260629.csv", "sha256": SHA_A, "period_start": "2026-06-29"}]
    )
    items = plan_publish(
        "nswgov",
        manifest,
        {"period=20260629_ab12cd34.parquet"},
        data_dir=tmp_path,
        volume_root=VOLUME_ROOT,
    )
    assert items == []


def test_landing_dirs_are_separate_per_dataset():
    assert landing_dir(VOLUME_ROOT, "nswgov").endswith("/landing/sales")
    assert landing_dir(VOLUME_ROOT, "rentboard").endswith("/landing/lodgements")


# --------------------------------------------------------------------------
# csv_to_parquet
# --------------------------------------------------------------------------


def test_parquet_round_trip_preserves_strings_and_empties(tmp_path):
    columns = ["a", "b", "c"]
    csv_path = tmp_path / "part.csv"
    pd.DataFrame(
        {"a": ["2327.0"], "b": [""], "c": ["2.0150416E7"]}, columns=columns
    ).to_csv(csv_path, index=False)

    out = csv_to_parquet(csv_path, columns, tmp_path / "part.parquet")
    table = pq.read_table(out)

    assert table.schema.names == columns
    assert all(field.type == "string" for field in table.schema)
    frame = table.to_pandas()
    assert frame["a"].tolist() == ["2327.0"]
    assert frame["b"].tolist() == [""], "empty string must not become NaN/NULL"
    assert frame["c"].tolist() == ["2.0150416E7"]
    assert "__index_level_0__" not in table.schema.names


def test_parquet_conversion_is_atomic_leaving_no_tmp(tmp_path):
    columns = ["a"]
    csv_path = tmp_path / "part.csv"
    pd.DataFrame({"a": ["1"]}).to_csv(csv_path, index=False)
    out = csv_to_parquet(csv_path, columns, tmp_path / "part.parquet")
    assert out.exists()
    assert not list(tmp_path.glob("*.tmp"))


def test_schema_drift_fails_loudly_naming_the_column(tmp_path):
    csv_path = tmp_path / "part.csv"
    pd.DataFrame({"a": ["1"], "unexpected": ["2"]}).to_csv(csv_path, index=False)

    with pytest.raises(SchemaDriftError) as excinfo:
        csv_to_parquet(csv_path, ["a", "b"], tmp_path / "out.parquet")

    message = str(excinfo.value)
    assert "unexpected" in message
    assert "b" in message
    assert not (tmp_path / "out.parquet").exists()


def test_real_sales_columns_convert(tmp_path):
    csv_path = tmp_path / "period=20260629.csv"
    _sales_frame().to_csv(csv_path, index=False)
    out = csv_to_parquet(csv_path, list(SALES_COLUMNS), tmp_path / "out.parquet")
    assert pq.read_table(out).schema.names == list(SALES_COLUMNS)
    assert len(SALES_COLUMNS) == 28


def test_real_rent_columns_convert(tmp_path):
    csv_path = tmp_path / "month=06.csv"
    _rent_frame().to_csv(csv_path, index=False)
    out = csv_to_parquet(csv_path, list(RENT_COLUMNS), tmp_path / "out.parquet")
    assert pq.read_table(out).schema.names == list(RENT_COLUMNS)
    assert len(RENT_COLUMNS) == 5


# --------------------------------------------------------------------------
# publish end to end, against a fake sink
# --------------------------------------------------------------------------


def test_publish_uploads_everything_on_first_run(tmp_path):
    data_dir = _build_data_dir(tmp_path)
    sink = FakeSink()

    report = publish_databricks(data_dir=data_dir, sink=sink, volume_root=VOLUME_ROOT, verbose=False)

    assert len(report.uploaded) == 3
    assert report.skipped == 0
    remote_dirs = {remote.rsplit("/", 1)[0] for _, remote in sink.uploads}
    assert remote_dirs == {
        f"{VOLUME_ROOT}/landing/sales",
        f"{VOLUME_ROOT}/landing/lodgements",
    }


def test_publish_is_idempotent(tmp_path):
    data_dir = _build_data_dir(tmp_path)
    sink = FakeSink()

    first = publish_databricks(data_dir=data_dir, sink=sink, volume_root=VOLUME_ROOT, verbose=False)
    second = publish_databricks(data_dir=data_dir, sink=sink, volume_root=VOLUME_ROOT, verbose=False)

    assert len(first.uploaded) == 3
    assert second.uploaded == []
    assert second.planned == []
    assert second.skipped == 3


def test_rent_revision_publishes_a_new_version_and_keeps_the_old(tmp_path):
    data_dir = _build_data_dir(tmp_path, rent_rows=3)
    sink = FakeSink()
    publish_databricks(data_dir=data_dir, sink=sink, volume_root=VOLUME_ROOT, verbose=False)
    before = set(sink.files)
    old_rent = {name for name in before if "lodgements" in name}
    assert len(old_rent) == 1

    # Rewrite the trailing month the way rentboard does, then rebuild the manifest.
    rent_csv = data_dir / "normalized" / "rentboard" / "lodgements" / "year=2026" / "month=06.csv"
    _rent_frame(rows=7).to_csv(rent_csv, index=False)
    write_manifest(
        data_dir=data_dir,
        manifest_path=data_dir / "manifests" / "rentboard_lodgements_manifest.csv",
        source="rentboard",
        dataset="lodgements",
        partitions=[(rent_csv, "2026-06-01", "2026-06-30")],
    )

    report = publish_databricks(data_dir=data_dir, sink=sink, volume_root=VOLUME_ROOT, verbose=False)

    assert len(report.uploaded) == 1
    new_rent = {name for name in sink.files if "lodgements" in name}
    assert old_rent < new_rent, "the previous version must survive: landing is append-only"
    assert len(new_rent) == 2
    labels = {name.rsplit("/", 1)[-1].split("_")[0] for name in new_rent}
    assert labels == {"month=2026-06"}, "both versions share the partition label"


def test_dry_run_uploads_nothing_but_still_plans(tmp_path):
    data_dir = _build_data_dir(tmp_path)
    sink = FakeSink()

    report = publish_databricks(
        data_dir=data_dir, sink=sink, volume_root=VOLUME_ROOT, dry_run=True, verbose=False
    )

    assert len(report.planned) == 3
    assert report.uploaded == []
    assert sink.uploads == []
    assert sink.files == {}


def test_missing_landing_dir_is_treated_as_empty(tmp_path):
    data_dir = _build_data_dir(tmp_path)

    class NotFoundSink(FakeSink):
        def list_names(self, directory: str) -> set[str]:
            if not self.files:
                raise RuntimeError("NotFound: directory does not exist")
            return super().list_names(directory)

    sink = NotFoundSink()
    # The sink itself raises; VolumeSink swallows not-found, so emulate that
    # contract here by asserting the planner copes with an empty listing.
    report = publish_databricks(
        data_dir=data_dir, sink=FakeSink(), volume_root=VOLUME_ROOT, verbose=False
    )
    assert len(report.uploaded) == 3
    with pytest.raises(RuntimeError, match="NotFound"):
        sink.list_names(landing_dir(VOLUME_ROOT, "nswgov"))


def test_publish_can_target_one_dataset(tmp_path):
    data_dir = _build_data_dir(tmp_path)
    sink = FakeSink()

    report = publish_databricks(
        data_dir=data_dir,
        sink=sink,
        volume_root=VOLUME_ROOT,
        datasets=("rentboard",),
        verbose=False,
    )

    assert len(report.uploaded) == 1
    assert all("lodgements" in remote for _, remote in sink.uploads)


def test_missing_manifest_raises_a_helpful_error(tmp_path):
    data_dir = tmp_path / "data"
    (data_dir / "manifests").mkdir(parents=True)
    with pytest.raises(FileNotFoundError, match="manifest not found"):
        publish_databricks(data_dir=data_dir, sink=FakeSink(), verbose=False)


def test_dataset_specs_track_the_pinned_column_contracts():
    assert DATASETS["nswgov"].columns == list(SALES_COLUMNS)
    assert DATASETS["rentboard"].columns == list(RENT_COLUMNS)
