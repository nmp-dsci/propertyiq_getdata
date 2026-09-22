-- staging.econ_series is the newest vintage per dataset: exactly one asof per dataset.
select dataset, count(distinct asof) as vintages
from {{ ref('stg_econ_series') }}
group by dataset
having count(distinct asof) <> 1
