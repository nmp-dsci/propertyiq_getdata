"""Regenerate dbt/seeds/econ_headline_series.csv from the loaded raw tables.

The seed is the curated map "which SDMX/RBA series is *the* unemployment
rate / mean dwelling price / cash rate" that lets a consumer pivot
``staging.econ_series`` to wide with one join (plan s03 §03). The rules below
are the curation; the CSV is their output, committed so dbt does not need
the database to seed and so a diff shows exactly which series changed.

Run after ``propertyiq-getdata db load``::

    uv run --env-file .env python scripts/econ_headline_seed.py
"""

from __future__ import annotations

import csv
import os
from pathlib import Path

import psycopg

OUT = Path(__file__).resolve().parents[1] / "dbt" / "seeds" / "econ_headline_series.csv"
COLUMNS = [
    "series_id",
    "dataset",
    "measure",
    "region",
    "adjustment",
    "freq",
    "unit",
    "description",
]

# (dataset, sql predicate over the raw table, measure expression, adjustment expression)
# `measure` names follow <thing>_<unit-ish suffix>; suffixes: _pct, _k (thousands),
# _m ($ millions), _n (count), _index.
RULES: list[tuple[str, str, str, str]] = [
    (
        "labour_force",
        "dim_measure in ('M3','M6','M13','M16') and dim_tsest in ('20','30')",
        "case dim_measure when 'M13' then 'unemployment_rate_pct' when 'M16' then 'employment_to_population_pct' "
        "when 'M3' then 'employed_persons_k' when 'M6' then 'unemployed_persons_k' end",
        "case dim_tsest when '20' then 'sa' when '30' then 'trend' else 'original' end",
    ),
    (
        "dwelling_values",
        "dim_measure in ('1','4','5')",
        "case dim_measure when '1' then 'dwelling_stock_value_m' when '4' then 'dwelling_count_k' "
        "when '5' then 'mean_dwelling_price_k' end",
        "'original'",
    ),
    (
        "dwelling_medians",
        "dim_measure in ('1','2','3','4')",
        "case dim_measure when '1' then 'house_transfers_n' when '2' then 'attached_transfers_n' "
        "when '3' then 'median_house_price_k' when '4' then 'median_attached_price_k' end",
        "'original'",
    ),
    (
        "cpi",
        "dim_index = '10001' and dim_tsest = '10' and dim_measure in ('1','2','3')",
        "case dim_measure when '1' then 'cpi_index' when '3' then 'cpi_yoy_pct' "
        "when '2' then case freq when 'Q' then 'cpi_qoq_pct' else 'cpi_mom_pct' end end",
        "'original'",
    ),
    (
        "wpi",
        "dim_measure in ('1','3') and dim_tsest in ('10','20')",
        "case dim_measure when '1' then 'wpi_index' when '3' then 'wpi_yoy_pct' end",
        "case dim_tsest when '20' then 'sa' else 'original' end",
    ),
    (
        "population",
        "dim_measure in ('1','3')",
        "case dim_measure when '1' then 'erp_persons' when '3' then 'erp_yoy_pct' end",
        "'original'",
    ),
    (
        "building_approvals",
        "dim_building_type in ('100','110','120','130')",
        "case dim_building_type when '100' then 'approvals_total_n' when '110' then 'approvals_houses_n' "
        "when '120' then 'approvals_townhouses_n' when '130' then 'approvals_apartments_n' end",
        "'original'",
    ),
    (
        "lending_housing",
        "dim_data_item = 'NEWCOMMITS'",
        "case dim_measure when 'FIN_NUM' then 'loan_commitments_n_' else 'loan_commitments_value_m_' end || "
        "case dim_housing_purpose when 'DV5167' then 'owner_occupier' when 'DV5167_FHB' then 'first_home_buyer' "
        "when 'DV5167_NONFHB' then 'owner_occupier_non_fhb' when 'DV5168' then 'investor' "
        "when 'DV5168_FHB' then 'investor_fhb' end",
        "case dim_tsest when '20' then 'sa' else 'original' end",
    ),
]

RBA: dict[str, str] = {
    "FIRMMCRT": "cash_rate_target_pct",
    "FIRMMCRI": "interbank_cash_rate_pct",
    "FIRMMBAB90": "bab_90d_pct",
    "FILRHLBVS": "housing_variable_standard_oo_pct",
    "FILRHLBVD": "housing_variable_discounted_oo_pct",
    "FILRHL3YF": "housing_3y_fixed_oo_pct",
    "FILRHLBVSI": "housing_variable_standard_inv_pct",
    "FILRHLBVDI": "housing_variable_discounted_inv_pct",
    "FILRHL3YFI": "housing_3y_fixed_inv_pct",
    "ARBAMPCNCRT": "cash_rate_target_decision_pct",
    "ARBAMPCCCR": "cash_rate_change_pct",
}


def main() -> None:
    rows: list[dict[str, str]] = []
    with (
        psycopg.connect(os.environ["PROPERTYIQ_DATABASE_URL"]) as conn,
        conn.cursor() as cur,
    ):
        for dataset, where, measure, adjustment in RULES:
            cur.execute(
                f"select distinct series_id, {measure}, region, {adjustment}, freq, unit, series_label "
                f"from raw.abs_ts_{dataset} where {where} and asof = (select max(asof) from raw.abs_ts_{dataset}) "
                "order by 1"
            )
            for series_id, m, region, adj, freq, unit, label in cur.fetchall():
                if m is None:
                    continue
                rows.append(
                    dict(
                        series_id=series_id,
                        dataset=dataset,
                        measure=m,
                        region=region,
                        adjustment=adj,
                        freq=freq,
                        unit=unit,
                        description=label,
                    )
                )
        for table in ("rba_cash_rate", "rba_lending_rates", "rba_rate_changes"):
            cur.execute(
                f"select distinct series_id, freq, unit, series_label from raw.{table} "
                f"where asof = (select max(asof) from raw.{table}) order by 1"
            )
            for series_id, freq, unit, label in cur.fetchall():
                if series_id in RBA:
                    rows.append(
                        dict(
                            series_id=series_id,
                            dataset=table,
                            measure=RBA[series_id],
                            region="AUS",
                            adjustment="original",
                            freq=freq,
                            unit=unit,
                            description=label,
                        )
                    )
    rows.sort(key=lambda r: (r["dataset"], r["measure"], r["region"], r["series_id"]))
    with OUT.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {OUT} ({len(rows)} series)")


if __name__ == "__main__":
    main()
