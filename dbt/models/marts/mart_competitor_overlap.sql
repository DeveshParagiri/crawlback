select
  graph_release_id,
  competitor_company,
  competitor_segment,
  competitor_referring_domain_count,
  omni_referring_domain_count,
  overlap_domain_count,
  competitor_only_domain_count,
  omni_only_domain_count,
  union_domain_count,
  round(jaccard_overlap, 4) as jaccard_overlap
from {{ ref('int_competitor_overlap') }}
