select
  graph_release_id,
  source_domain as referring_domain,
  target_company,
  target_segment,
  target_domains,
  raw_edge_rows,
  total_edge_weight,
  source_domain_rank_bucket,
  source_high_authority_flag,
  source_domain_rank_position,
  source_domain_harmonic_centrality,
  source_domain_pagerank,
  loaded_at
from {{ ref('int_referring_domain_company') }}
