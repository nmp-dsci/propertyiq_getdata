{{
  config(
    materialized='table',
    alias='econ_series_vintages',
    indexes=[
      {'columns': ['series_id', 'period_start', 'asof'], 'unique': True},
      {'columns': ['dataset', 'asof']},
    ]
  )
}}

-- Every vintage of every economic series, typed (decision D4). One row per
-- (series_id, period_start, asof). Publishers revise history (seasonal
-- re-estimation, p -> r flags, index rebases), so "what did the ABS say in
-- March" is a real question; this table answers it. For the current view use
-- staging.econ_series.
with unioned as (
    {{ econ_union(latest_only=false) }}
)
select
    *,
    date_trunc('month', period_start)::date   as period_month,
    date_trunc('quarter', period_start)::date as period_quarter
from unioned
