"""Inspect a published Parquet partition — locally, or straight from the volume.

The publish converts each partition in a temp directory and deletes it after
upload, so nothing is left on disk to look at. This fetches a file back out of
the Unity Catalog volume (or reads one you already have) and shows what it
actually contains: schema, compression, row groups, and sample rows.

    # list what has been published
    uv run python scripts/inspect_parquet.py --list
    uv run python scripts/inspect_parquet.py --list --dataset rentboard

    # inspect the newest published partition of a dataset
    uv run python scripts/inspect_parquet.py --latest
    uv run python scripts/inspect_parquet.py --latest --dataset rentboard

    # inspect one by name, or a local file
    uv run python scripts/inspect_parquet.py period=20260629_7e9931d0.parquet
    uv run python scripts/inspect_parquet.py ./some_local.parquet

    # prove it round-trips against the CSV partition it was made from
    uv run python scripts/inspect_parquet.py --latest --verify
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from propertyiq_getdata.core.paths import get_paths  # noqa: E402
from propertyiq_getdata.sinks.databricks import (  # noqa: E402
    DEFAULT_VOLUME_ROOT,
    landing_dir,
)


def _client(profile: str):
    from databricks.sdk import WorkspaceClient

    return WorkspaceClient(profile=profile)


def list_published(dataset: str, profile: str, volume_root: str) -> list[str]:
    directory = landing_dir(volume_root, dataset)
    entries = _client(profile).files.list_directory_contents(directory)
    return sorted(entry.name for entry in entries)


def fetch(name: str, dataset: str, profile: str, volume_root: str, into: Path) -> Path:
    remote = f"{landing_dir(volume_root, dataset)}/{name}"
    local = into / name
    response = _client(profile).files.download(remote)
    local.write_bytes(response.contents.read())
    return local


def describe(path: Path, *, rows: int) -> pq.ParquetFile:
    parquet = pq.ParquetFile(path)
    meta = parquet.metadata
    schema = parquet.schema_arrow

    size = path.stat().st_size
    print(f"file          {path.name}")
    print(f"size          {size:,} bytes ({size / 1024:.1f} KiB)")
    print(f"rows          {meta.num_rows:,}")
    print(f"columns       {meta.num_columns}")
    print(f"row groups    {meta.num_row_groups}")
    print(f"created by    {meta.created_by}")

    compressions = {
        meta.row_group(g).column(c).compression
        for g in range(meta.num_row_groups)
        for c in range(meta.num_columns)
    }
    print(f"compression   {', '.join(sorted(compressions))}")

    non_string = [field.name for field in schema if field.type != "string"]
    print(f"all-string    {'yes' if not non_string else 'NO -> ' + str(non_string)}")
    index_cols = [name for name in schema.names if name.startswith("__index_level")]
    print(f"index column  {'none' if not index_cols else index_cols}")

    print("\nschema")
    for field in schema:
        print(f"  {field.name:<15} {field.type}")

    frame = parquet.read().to_pandas()
    print(f"\nfirst {min(rows, len(frame))} rows")
    with pd.option_context("display.max_columns", None, "display.width", 200):
        print(frame.head(rows).to_string())

    return parquet


def verify_against_csv(path: Path, dataset: str, data_dir: str | None) -> int:
    """Re-read the CSV this file was built from and compare, cell for cell."""
    paths = get_paths(data_dir)
    label = path.name.rsplit("_", 1)[0]

    if dataset == "nswgov":
        source = paths.nswgov_sales_dir / f"{label}.csv"
    else:
        year, month = label.removeprefix("month=").split("-")
        source = paths.rentboard_lodgements_dir / f"year={year}" / f"month={month}.csv"

    if not source.exists():
        print(f"\nverify: no local CSV at {source} — skipping")
        return 0

    csv = pd.read_csv(source, dtype=str, keep_default_na=False)
    parquet = pq.read_table(path).to_pandas()

    same_shape = csv.shape == parquet.shape
    same_columns = list(csv.columns) == list(parquet.columns)
    identical = same_shape and same_columns and parquet.equals(csv)

    print(f"\nverify against {source.name}")
    print(f"  csv rows/cols      {csv.shape}")
    print(f"  parquet rows/cols  {parquet.shape}")
    print(f"  column order match {same_columns}")
    print(f"  every cell equal   {identical}")
    print(f"  size on disk       {source.stat().st_size:,} -> {path.stat().st_size:,} bytes")
    if not identical:
        print("  MISMATCH — the published file does not match its source partition")
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("name", nargs="?", help="File name in the volume, or a local .parquet path.")
    parser.add_argument("--dataset", choices=["nswgov", "rentboard"], default="nswgov")
    parser.add_argument("--profile", default="DEFAULT")
    parser.add_argument("--volume-root", default=DEFAULT_VOLUME_ROOT)
    parser.add_argument("--data-dir", default=None)
    parser.add_argument("--list", action="store_true", help="List published files and exit.")
    parser.add_argument("--latest", action="store_true", help="Inspect the newest published file.")
    parser.add_argument("--rows", type=int, default=5, help="Sample rows to print (default 5).")
    parser.add_argument("--verify", action="store_true", help="Diff against the source CSV.")
    args = parser.parse_args(argv)

    if args.list:
        names = list_published(args.dataset, args.profile, args.volume_root)
        print(f"{len(names)} published under {landing_dir(args.volume_root, args.dataset)}\n")
        for name in names:
            print(f"  {name}")
        return 0

    local = Path(args.name) if args.name else None
    if local and local.exists():
        describe(local, rows=args.rows)
        return verify_against_csv(local, args.dataset, args.data_dir) if args.verify else 0

    name = args.name
    if args.latest or not name:
        published = list_published(args.dataset, args.profile, args.volume_root)
        if not published:
            print("nothing published yet", file=sys.stderr)
            return 2
        name = published[-1]
        print(f"(newest {args.dataset} partition: {name})\n")

    with tempfile.TemporaryDirectory() as tmp:
        path = fetch(name, args.dataset, args.profile, args.volume_root, Path(tmp))
        describe(path, rows=args.rows)
        return verify_against_csv(path, args.dataset, args.data_dir) if args.verify else 0


if __name__ == "__main__":
    raise SystemExit(main())
