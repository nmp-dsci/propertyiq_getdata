-- staging.property_rent must cover enough postcodes to support postcode-level
-- analysis downstream. Returns a row (failing) if too thin.
select count(distinct postcode) as postcode_count
from {{ ref('stg_property_rent') }}
having count(distinct postcode) < 10
