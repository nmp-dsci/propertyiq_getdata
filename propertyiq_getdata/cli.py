from __future__ import annotations

import argparse

from .audit import print_audit
from .sources.abs import (
    DEFAULT_CENSUS_YEAR,
    DEFAULT_STATE,
    GEOGRAPHY,
    extract_abs,
    pull_abs,
    refresh_abs_poa_manifest,
    transform_abs,
    update_abs,
)
from .sources.nswgov import (
    export_legacy_nswgov,
    extract_nswgov,
    migrate_legacy_nswgov,
    pull_nswgov,
    refresh_nswgov_manifest,
    transform_nswgov,
    update_nswgov,
)
from .sources.rentboard import (
    export_legacy_rentboard,
    migrate_legacy_rentboard,
    refresh_rentboard_manifest,
    update_rentboard,
)


def build_parser() -> argparse.ArgumentParser:
    data_parent = argparse.ArgumentParser(add_help=False)
    data_parent.add_argument("--data-dir", default=None, help="Data directory. Defaults to repo-local data/.")

    parser = argparse.ArgumentParser(prog="propertyiq_getdata", parents=[data_parent])
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("audit", parents=[data_parent], help="Print current trusted-output summary.")

    nswgov = subparsers.add_parser("nswgov", parents=[data_parent], help="Run NSW Valuer General stages.")
    nswgov_sub = nswgov.add_subparsers(dest="stage", required=True)
    nswgov_pull = nswgov_sub.add_parser("pull", parents=[data_parent])
    nswgov_pull.add_argument("--term", action="append", choices=["yearly", "weekly"], help="Limit to one or more terms.")
    nswgov_pull.add_argument("--all-periods", action="store_true", help="Download every discovered period instead of periods needed after the trusted final CSV.")
    nswgov_pull.add_argument("--dry-run", action="store_true")
    nswgov_extract = nswgov_sub.add_parser("extract", parents=[data_parent])
    nswgov_extract.add_argument("--all-periods", action="store_true", help="Extract every raw period instead of periods needed after the trusted final CSV.")
    nswgov_sub.add_parser("transform", parents=[data_parent])
    nswgov_sub.add_parser("manifest", parents=[data_parent], help="Rebuild the NSWGOV partition manifest.")
    nswgov_sub.add_parser("migrate-legacy", parents=[data_parent], help="Split the old nswgov_df.csv into period partitions.")
    nswgov_sub.add_parser("export-legacy", parents=[data_parent], help="Stack NSWGOV partitions into the old nswgov_df.csv shape.")
    nswgov_update = nswgov_sub.add_parser("update", parents=[data_parent])
    nswgov_update.add_argument("--all-periods", action="store_true", help="Download every discovered period instead of periods needed after the trusted final CSV.")
    nswgov_update.add_argument("--dry-run", action="store_true")

    rentboard = subparsers.add_parser("rentboard", parents=[data_parent], help="Run NSW rental bond update.")
    rentboard_sub = rentboard.add_subparsers(dest="stage", required=True)
    rentboard_update = rentboard_sub.add_parser("update", parents=[data_parent])
    rentboard_update.add_argument("--dry-run", action="store_true")
    rentboard_sub.add_parser("manifest", parents=[data_parent], help="Rebuild the rentboard partition manifest.")
    rentboard_sub.add_parser("migrate-legacy", parents=[data_parent], help="Split the old rentboard_df.csv into monthly partitions.")
    rentboard_sub.add_parser("export-legacy", parents=[data_parent], help="Stack rentboard partitions into the old rentboard_df.csv shape.")

    abs_parent = argparse.ArgumentParser(add_help=False)
    abs_parent.add_argument("--census-year", type=int, default=DEFAULT_CENSUS_YEAR, help=f"Census year. Defaults to {DEFAULT_CENSUS_YEAR}.")
    abs_parent.add_argument("--state", default=DEFAULT_STATE, help=f"State DataPack to pull. Defaults to {DEFAULT_STATE}.")
    abs_parent.add_argument("--geography", default=GEOGRAPHY, help=f"ASGS geography level. Defaults to {GEOGRAPHY}.")

    abs_cmd = subparsers.add_parser("abs", parents=[data_parent], help="Run ABS Census GCP DataPack stages.")
    abs_sub = abs_cmd.add_subparsers(dest="stage", required=True)
    abs_pull = abs_sub.add_parser("pull", parents=[data_parent, abs_parent])
    abs_pull.add_argument("--force", action="store_true", help="Re-download and re-extract even if already present.")
    abs_pull.add_argument("--dry-run", action="store_true")
    abs_sub.add_parser("extract", parents=[data_parent, abs_parent])
    abs_sub.add_parser("transform", parents=[data_parent, abs_parent])
    abs_sub.add_parser("manifest", parents=[data_parent], help="Rebuild the ABS POA partition manifest.")
    abs_update = abs_sub.add_parser("update", parents=[data_parent, abs_parent])
    abs_update.add_argument("--force", action="store_true", help="Re-download and re-extract even if already present.")
    abs_update.add_argument("--dry-run", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "audit":
        print_audit(data_dir=args.data_dir)
        return 0
    if args.command == "nswgov":
        if args.stage == "pull":
            terms = args.term if args.term else ("yearly", "weekly")
            print(
                pull_nswgov(
                    data_dir=args.data_dir,
                    terms=terms,
                    new_only=not args.all_periods,
                    dry_run=args.dry_run,
                ).to_string(index=False)
            )
            return 0
        if args.stage == "extract":
            print(extract_nswgov(data_dir=args.data_dir, new_only=not args.all_periods).to_string(index=False))
            return 0
        if args.stage == "transform":
            print(transform_nswgov(data_dir=args.data_dir).to_string(index=False))
            return 0
        if args.stage == "manifest":
            print(refresh_nswgov_manifest(data_dir=args.data_dir).to_string(index=False))
            return 0
        if args.stage == "migrate-legacy":
            print(migrate_legacy_nswgov(data_dir=args.data_dir).to_string(index=False))
            return 0
        if args.stage == "export-legacy":
            print(export_legacy_nswgov(data_dir=args.data_dir).to_string(index=False))
            return 0
        if args.stage == "update":
            update_nswgov(data_dir=args.data_dir, dry_run=args.dry_run, new_only=not args.all_periods)
            return 0
    if args.command == "rentboard":
        if args.stage == "update":
            print(update_rentboard(data_dir=args.data_dir, dry_run=args.dry_run).to_string(index=False))
            return 0
        if args.stage == "manifest":
            print(refresh_rentboard_manifest(data_dir=args.data_dir).to_string(index=False))
            return 0
        if args.stage == "migrate-legacy":
            print(migrate_legacy_rentboard(data_dir=args.data_dir).to_string(index=False))
            return 0
        if args.stage == "export-legacy":
            print(export_legacy_rentboard(data_dir=args.data_dir).to_string(index=False))
            return 0
    if args.command == "abs":
        if args.stage == "pull":
            print(
                pull_abs(
                    data_dir=args.data_dir,
                    census_year=args.census_year,
                    state=args.state,
                    geography=args.geography,
                    dry_run=args.dry_run,
                    force=args.force,
                ).to_string(index=False)
            )
            return 0
        if args.stage == "extract":
            print(
                extract_abs(
                    data_dir=args.data_dir, census_year=args.census_year, state=args.state, geography=args.geography
                ).to_string(index=False)
            )
            return 0
        if args.stage == "transform":
            print(
                transform_abs(
                    data_dir=args.data_dir, census_year=args.census_year, state=args.state, geography=args.geography
                ).to_string(index=False)
            )
            return 0
        if args.stage == "manifest":
            print(refresh_abs_poa_manifest(data_dir=args.data_dir).to_string(index=False))
            return 0
        if args.stage == "update":
            update_abs(
                data_dir=args.data_dir,
                census_year=args.census_year,
                state=args.state,
                geography=args.geography,
                dry_run=args.dry_run,
                force=args.force,
            )
            return 0
    raise RuntimeError(f"Unhandled command: {args}")
