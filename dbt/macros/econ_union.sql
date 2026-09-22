{#-
  UNION the 11 economic raw tables (8 abs_ts_* + 3 rba_*) onto the shared
  CORE_COLUMNS contract (propertyiq_getdata/core/series.py), typed.

  Each dataflow lands with its own ragged set of `dim_*` columns (the SDMX
  dimensions of that dataflow). They are folded into one `dims` jsonb so the
  long table has a fixed shape while nothing is lost: consumers filter with
  `dims->>'measure' = 'M13'` or, more usefully, join the curated
  `econ_headline_series` seed on series_id.

  `dim_*` columns are discovered from the relation at compile time, so the
  raw tables must exist (run `db load` before `db dbt`).
-#}
{% macro econ_union(latest_only) -%}
{%- set tables = [
    'abs_ts_dwelling_values', 'abs_ts_dwelling_medians', 'abs_ts_cpi', 'abs_ts_labour_force',
    'abs_ts_wpi', 'abs_ts_lending_housing', 'abs_ts_building_approvals', 'abs_ts_population',
    'rba_cash_rate', 'rba_lending_rates', 'rba_rate_changes'
] -%}
{%- for table in tables %}
{%- set rel = source('raw', table) %}
{%- set dims = [] %}
{%- if execute %}
  {%- for col in adapter.get_columns_in_relation(rel) if col.name.startswith('dim_') and not col.name.endswith('_label') %}
    {%- do dims.append(col.name) %}
  {%- endfor %}
{%- endif %}
select
    source,
    dataset,
    series_id,
    series_label,
    dataflow,
    freq,
    time_period,
    period_start::date                              as period_start,
    nullif(value, '')::numeric                      as value,
    nullif(unit, '')                                as unit,
    nullif(unit_mult, '')::int                      as unit_mult,
    nullif(obs_status, '')                          as obs_status,
    nullif(obs_comment, '')                         as obs_comment,
    nullif(region, '')                              as region,
    nullif(base_period, '')                         as base_period,
    asof::date                                      as asof,
    {%- if dims %}
    jsonb_strip_nulls(jsonb_build_object(
        {%- for d in dims %}
        '{{ d[4:] }}', nullif({{ d }}, ''), '{{ d[4:] }}_label', nullif({{ d }}_label, ''){{ "," if not loop.last }}
        {%- endfor %}
    ))                                              as dims
    {%- else %}
    '{}'::jsonb                                     as dims
    {%- endif %}
from {{ rel }}
{%- if latest_only %}
where asof = (select max(asof) from {{ rel }})
{%- endif %}
{{ "union all" if not loop.last }}
{%- endfor %}
{%- endmacro %}
