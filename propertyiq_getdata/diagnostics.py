from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from .paths import get_paths


NSWGOV_COMPARE_COLUMNS = ["locality", "postcode", "contract_dt", "sale_price"]


def latest_backup_file(data_dir: str | Path | None = None, filename: str = "nswgov_df.csv") -> Path:
    paths = get_paths(data_dir)
    backup_dir = paths.data_dir / "backups"
    candidates = sorted(backup_dir.glob(f"*/{filename}"))
    if not candidates:
        raise FileNotFoundError(f"No backup {filename} found under {backup_dir}")
    return candidates[-1]


def _normalise_postcode(value: str | int | float | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith(".0"):
        text = text[:-2]
    return text


def filter_nswgov_frame(df: pd.DataFrame, postcode: str | None = None, suburb: str | None = None) -> pd.DataFrame:
    out = df.copy()
    if postcode:
        postcode = _normalise_postcode(postcode)
        out = out[out["postcode"].map(_normalise_postcode) == postcode]
    if suburb:
        suburb_norm = suburb.strip().upper()
        out = out[out["locality"].fillna("").str.strip().str.upper() == suburb_norm]
    return out


def monthly_average_sale_price(df: pd.DataFrame, source: str) -> pd.DataFrame:
    out = df.copy()
    out["sale_price"] = pd.to_numeric(out["sale_price"], errors="coerce")
    out["contract_dt"] = out["contract_dt"].astype(str).str.extract(r"(\d{8})", expand=False)
    out["contract_month"] = pd.to_datetime(out["contract_dt"], format="%Y%m%d", errors="coerce").dt.to_period("M").dt.to_timestamp()
    out = out.dropna(subset=["contract_month", "sale_price"])
    if out.empty:
        return pd.DataFrame(columns=["source", "contract_month", "avg_sale_price", "sales"])
    grouped = (
        out.groupby("contract_month", as_index=False)
        .agg(avg_sale_price=("sale_price", "mean"), sales=("sale_price", "size"))
        .sort_values("contract_month")
    )
    grouped.insert(0, "source", source)
    return grouped


def read_filtered_monthly_average(
    csv_path: str | Path,
    source: str,
    postcode: str | None = None,
    suburb: str | None = None,
    chunksize: int = 250_000,
) -> pd.DataFrame:
    csv_path = Path(csv_path)
    pieces = []
    for chunk in pd.read_csv(csv_path, usecols=NSWGOV_COMPARE_COLUMNS, dtype=str, chunksize=chunksize):
        filtered = filter_nswgov_frame(chunk, postcode=postcode, suburb=suburb)
        if not filtered.empty:
            pieces.append(filtered)
    if not pieces:
        return pd.DataFrame(columns=["source", "contract_month", "avg_sale_price", "sales"])
    return monthly_average_sale_price(pd.concat(pieces, ignore_index=True), source=source)


def compare_nswgov_latest_backup(
    latest_csv: str | Path,
    backup_csv: str | Path,
    postcode: str | None = None,
    suburb: str | None = None,
) -> pd.DataFrame:
    frames = [
        read_filtered_monthly_average(backup_csv, source="backup", postcode=postcode, suburb=suburb),
        read_filtered_monthly_average(latest_csv, source="latest", postcode=postcode, suburb=suburb),
    ]
    return pd.concat(frames, ignore_index=True)


def plot_comparison(comparison: pd.DataFrame, output_path: str | Path, title: str) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(12, 6))
    for source, source_df in comparison.groupby("source"):
        source_df = source_df.sort_values("contract_month")
        ax.plot(source_df["contract_month"], source_df["avg_sale_price"], marker="o", linewidth=1.8, label=source)
    ax.set_title(title)
    ax.set_xlabel("Contract month")
    ax.set_ylabel("Average sale price")
    ax.grid(True, alpha=0.3)
    ax.legend(title="Source")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output_path, dpi=160)
    plt.close(fig)
    return output_path


def build_compare_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare latest NSWGOV sales data to a backup by monthly average sale price.")
    parser.add_argument("--data-dir", default=None, help="Data directory. Defaults to repo-local data/.")
    parser.add_argument("--latest-csv", default=None, help="Latest nswgov_df.csv. Defaults to data/nswgov_df.csv.")
    parser.add_argument("--backup-csv", default=None, help="Backup nswgov_df.csv. Defaults to newest data/backups/*/nswgov_df.csv.")
    parser.add_argument("--postcode", default=None, help="Filter to one postcode, e.g. 2076.")
    parser.add_argument("--suburb", default=None, help="Filter to one NSWGOV locality/suburb, e.g. HORNSBY.")
    parser.add_argument("--out", default=None, help="Output PNG path. Defaults to data/diagnostics/...")
    return parser


def compare_main(argv: list[str] | None = None) -> int:
    args = build_compare_parser().parse_args(argv)
    if not args.postcode and not args.suburb:
        raise SystemExit("Provide --postcode or --suburb so the comparison is scoped.")

    paths = get_paths(args.data_dir)
    latest_csv = Path(args.latest_csv) if args.latest_csv else paths.nswgov_final
    backup_csv = Path(args.backup_csv) if args.backup_csv else latest_backup_file(paths.data_dir)
    filter_label = args.suburb or args.postcode
    safe_filter = "".join(ch if ch.isalnum() else "_" for ch in str(filter_label).lower()).strip("_")
    output_path = Path(args.out) if args.out else paths.data_dir / "diagnostics" / f"nswgov_latest_vs_backup_{safe_filter}.png"

    comparison = compare_nswgov_latest_backup(
        latest_csv=latest_csv,
        backup_csv=backup_csv,
        postcode=args.postcode,
        suburb=args.suburb,
    )
    if comparison.empty:
        raise SystemExit("No matching NSWGOV sales rows found for the requested filter.")

    title_filter = f"postcode {args.postcode}" if args.postcode else f"suburb {args.suburb}"
    output_path = plot_comparison(comparison, output_path, f"NSWGOV average sale price by month: {title_filter}")
    print(comparison.tail(24).to_string(index=False))
    print(f"\nChart written to {output_path}")
    return 0
