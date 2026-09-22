{#-
  Snapshot datasets (abs_ts_*, rba_*) keep every `asof` vintage in raw
  (decision D4). "Latest" is the newest vintage *per dataset*, not per row --
  a series that the publisher dropped from a later release should disappear,
  not linger from an older snapshot.
-#}
{% macro latest_vintage(relation) -%}
    select * from {{ relation }}
    where asof = (select max(asof) from {{ relation }})
{%- endmacro %}
