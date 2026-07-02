from __future__ import annotations

import argparse

from .audit import print_audit
from .nswgov import extract_nswgov, pull_nswgov, transform_nswgov, update_nswgov
from .rentboard import update_rentboard


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
    nswgov_update = nswgov_sub.add_parser("update", parents=[data_parent])
    nswgov_update.add_argument("--all-periods", action="store_true", help="Download every discovered period instead of periods needed after the trusted final CSV.")
    nswgov_update.add_argument("--dry-run", action="store_true")

    rentboard = subparsers.add_parser("rentboard", parents=[data_parent], help="Run NSW rental bond update.")
    rentboard_sub = rentboard.add_subparsers(dest="stage", required=True)
    rentboard_update = rentboard_sub.add_parser("update", parents=[data_parent])
    rentboard_update.add_argument("--dry-run", action="store_true")
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
        if args.stage == "update":
            update_nswgov(data_dir=args.data_dir, dry_run=args.dry_run, new_only=not args.all_periods)
            return 0
    if args.command == "rentboard" and args.stage == "update":
        print(update_rentboard(data_dir=args.data_dir, dry_run=args.dry_run).to_string(index=False))
        return 0
    raise RuntimeError(f"Unhandled command: {args}")
