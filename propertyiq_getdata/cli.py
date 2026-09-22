from __future__ import annotations

import argparse

from .audit import print_audit
from .db.registry import LOAD_KEYS
from .sinks.databricks import DEFAULT_VOLUME_ROOT, publish_databricks
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
from .sources.abs_ts import (
    SERIES as ABS_TS_SERIES,
    pull_abs_ts,
    refresh_abs_ts_manifest,
    transform_abs_ts,
    update_abs_ts,
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
from .sources.rba import (
    TABLES as RBA_TABLES,
    pull_rba,
    refresh_rba_manifest,
    transform_rba,
    update_rba,
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

    publish = subparsers.add_parser("publish", parents=[data_parent], help="Publish partitions to an external target.")
    publish_sub = publish.add_subparsers(dest="target", required=True)
    publish_databricks_parser = publish_sub.add_parser(
        "databricks",
        parents=[data_parent],
        help="Upload new or changed partitions to a Unity Catalog volume as Parquet.",
    )
    publish_databricks_parser.add_argument("--dataset", choices=["nswgov", "rentboard", "all"], default="all")
    publish_databricks_parser.add_argument("--profile", default="DEFAULT", help="~/.databrickscfg profile name.")
    publish_databricks_parser.add_argument("--volume-root", default=DEFAULT_VOLUME_ROOT)
    publish_databricks_parser.add_argument("--dry-run", action="store_true", help="Print the plan, upload nothing.")
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

    # abs-ts and rba share one snapshot-per-release shape: pull | transform | manifest | update.
    def add_snapshot_source(name: str, help_text: str, choices: list[str]) -> None:
        select = argparse.ArgumentParser(add_help=False)
        select.add_argument(
            "--dataset",
            action="append",
            choices=choices,
            metavar="DATASET",
            help=f"Restrict to one dataset (repeatable). Choices: {', '.join(choices)}. Default: all.",
        )
        select.add_argument("--asof", help="Snapshot date YYYY-MM-DD. Default: today (UTC).")
        fetch = argparse.ArgumentParser(add_help=False)
        fetch.add_argument("--force", action="store_true", help="Re-download even if today's raw file exists.")
        fetch.add_argument("--dry-run", action="store_true")

        command = subparsers.add_parser(name, parents=[data_parent], help=help_text)
        stages = command.add_subparsers(dest="stage", required=True)
        stages.add_parser("pull", parents=[data_parent, select, fetch], help="Download raw files verbatim.")
        stages.add_parser("transform", parents=[data_parent, select], help="Normalize the newest raw pull into a snapshot.")
        stages.add_parser("manifest", parents=[data_parent], help=f"Rebuild the {name} snapshot manifest.")
        stages.add_parser("update", parents=[data_parent, select, fetch], help="pull + transform.")

    add_snapshot_source("abs-ts", "Run ABS Data API time-series stages.", list(ABS_TS_SERIES))
    add_snapshot_source("rba", "Run RBA statistical-table stages.", list(RBA_TABLES))

    # Central Postgres: land the manifests in raw, build staging with dbt.
    db_select = argparse.ArgumentParser(add_help=False)
    db_select.add_argument(
        "--dataset",
        action="append",
        metavar="SOURCE[/DATASET]",
        help=f"Restrict to a source or source/dataset (repeatable). Choices: {', '.join(LOAD_KEYS)}. Default: all.",
    )
    db_select.add_argument("--full-refresh", action="store_true", help="Truncate the raw table(s) and reload every partition.")
    db_select.add_argument("--dry-run", action="store_true", help="Print the partition plan without touching the database.")
    db = subparsers.add_parser("db", parents=[data_parent], help="Load into the central Postgres and run dbt.")
    db_stages = db.add_subparsers(dest="stage", required=True)
    db_stages.add_parser("init", parents=[data_parent], help="Create schemas, meta tables and grants (superuser, once).")
    db_stages.add_parser("load", parents=[data_parent, db_select], help="Manifests -> raw (incremental by sha256).")
    db_dbt = db_stages.add_parser("dbt", parents=[data_parent], help="Run the dbt project against staging.")
    db_dbt.add_argument("target", nargs="?", default="all", choices=["seed", "build", "docs", "all"])
    db_stages.add_parser("update", parents=[data_parent, db_select], help="load + dbt seed/build/docs, recorded as one run.")
    db_stages.add_parser("smoke", parents=[data_parent], help="Zero-LLM check as the read-only role (platform `make check`).")
    db_fixture = db_stages.add_parser("export-fixture", parents=[data_parent], help="Small staging SQL fixture for consumers' CI.")
    db_fixture.add_argument("--out", default="tests/fixtures/db/propertyiq_staging.sql")
    db_fixture.add_argument("--limit", type=int, default=500)

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
    if args.command == "publish":
        if args.target == "databricks":
            datasets = ("nswgov", "rentboard") if args.dataset == "all" else (args.dataset,)
            report = publish_databricks(
                data_dir=args.data_dir,
                volume_root=args.volume_root,
                profile=args.profile,
                datasets=datasets,
                dry_run=args.dry_run,
            )
            print(report.summary())
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
    snapshot_sources = {
        "abs-ts": (pull_abs_ts, transform_abs_ts, refresh_abs_ts_manifest, update_abs_ts),
        "rba": (pull_rba, transform_rba, refresh_rba_manifest, update_rba),
    }
    if args.command in snapshot_sources:
        pull, transform, manifest, update = snapshot_sources[args.command]
        if args.stage == "pull":
            report = pull(data_dir=args.data_dir, datasets=args.dataset, asof=args.asof, force=args.force, dry_run=args.dry_run)
        elif args.stage == "transform":
            report = transform(data_dir=args.data_dir, datasets=args.dataset, asof=args.asof)
        elif args.stage == "manifest":
            report = manifest(data_dir=args.data_dir)
        else:
            report = update(data_dir=args.data_dir, datasets=args.dataset, asof=args.asof, force=args.force, dry_run=args.dry_run)
        print(report.to_string(index=False))
        return 0
    if args.command == "db":
        from .db import export_fixture, init_db, run_dbt_stage, smoke, update_db
        from .db.pipeline import load_db

        if args.stage == "init":
            init_db()
        elif args.stage == "load":
            report = load_db(data_dir=args.data_dir, datasets=args.dataset, full_refresh=args.full_refresh, dry_run=args.dry_run)
            print(report.groupby(["table", "status"]).size().to_string())
        elif args.stage == "dbt":
            passed, total = run_dbt_stage(args.target)
            print(f"dbt tests: {passed}/{total}")
        elif args.stage == "update":
            report = update_db(data_dir=args.data_dir, datasets=args.dataset, full_refresh=args.full_refresh, dry_run=args.dry_run)
            print(report.groupby(["table", "status"]).size().to_string())
        elif args.stage == "smoke":
            return 0 if smoke() else 1
        else:
            print(export_fixture(args.out, limit=args.limit))
        return 0
    raise RuntimeError(f"Unhandled command: {args}")
