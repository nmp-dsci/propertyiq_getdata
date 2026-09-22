-- staging.property_sales must cover enough postcodes to support postcode-level
-- analysis downstream. Returns a row (failing) if too thin.
select count(distinct postcode) as postcode_count
from {{ ref('stg_property_sales') }}
having count(distinct postcode) < 10
