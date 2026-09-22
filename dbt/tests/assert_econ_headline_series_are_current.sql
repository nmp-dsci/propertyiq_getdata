-- Every curated headline series must still be published: an observation in
-- the last 2 years of its dataset's newest period. Catches an ABS key change
-- or a dataflow the publisher discontinued (RPPI, CPI_M did exactly that).
-- Old building-approvals dataflows are expected to end; they are excluded.
with latest as (
    select dataset, max(period_start) as newest from {{ ref('stg_econ_series') }} group by dataset
),
last_obs as (
    select series_id, max(period_start) as last_period from {{ ref('stg_econ_series') }} group by series_id
)
select h.series_id, h.measure, o.last_period, l.newest
from {{ ref('econ_headline_series') }} h
join latest l on l.dataset = h.dataset
left join last_obs o on o.series_id = h.series_id
where h.series_id not like 'BA_SA2_2%'
  and (o.last_period is null or o.last_period < l.newest - interval '2 years')
