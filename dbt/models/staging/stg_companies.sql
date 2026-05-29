select
  company,
  role,
  segment,
  domain
from {{ ref('companies') }}
