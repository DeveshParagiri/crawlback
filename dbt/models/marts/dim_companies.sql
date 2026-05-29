select
  company,
  role,
  segment,
  string_agg(domain, ', ' order by domain) as domains
from {{ ref('stg_companies') }}
group by
  company,
  role,
  segment
