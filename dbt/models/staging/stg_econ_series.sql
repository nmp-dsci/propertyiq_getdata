{{
  config(
    materialized='table',
    alias='econ_series',
    indexes=[
      {'columns': ['series_id', 'period_start'], 'unique': True},
      {'columns': ['dataset', 'region', 'period_start']},
    ]
  )
}}

-- The current statement of every economic series: the newest `asof` vintage
-- of each dataset (see macro latest_vintage for why per-dataset, not per-row).
-- One row per (series_id, period_start), long format. Pivot to wide by
-- joining staging.econ_headline_series on series_id -- that seed names the
-- headline measures (unemployment_rate_pct, mean_dwelling_price_k,
-- cash_rate_target_pct, ...) so nobody has to know SDMX keys.
--
-- building_approvals is stitched from three ABS dataflows whose months
-- overlap; series_id carries the dataflow, so a consumer picking one month
-- should prefer the newest dataflow (BA_SA2 > BA_SA2_2016-21 > BA_SA2_201116).
with unioned as (
    {{ econ_union(latest_only=true) }}
)
select
    *,
    date_trunc('month', period_start)::date   as period_month,
    date_trunc('quarter', period_start)::date as period_quarter
from unioned
