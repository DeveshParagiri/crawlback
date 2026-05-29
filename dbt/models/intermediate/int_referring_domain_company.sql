select
  edges.graph_release_id,
  edges.source_domain,
  edges.target_company,
  edges.target_segment,
  edges.target_domains,
  edges.raw_edge_rows,
  edges.total_edge_weight,
  coalesce(edges.source_domain_rank_bucket, ranks.best_rank_bucket) as source_domain_rank_bucket,
  coalesce(edges.source_high_authority_flag, ranks.high_authority_rank_flag, false) as source_high_authority_flag,
  ranks.best_rank_position as source_domain_rank_position,
  ranks.harmonic_centrality as source_domain_harmonic_centrality,
  ranks.pagerank as source_domain_pagerank,
  edges.loaded_at
from {{ ref('stg_domain_edges') }} as edges
left join {{ ref('int_domain_rank_rollup') }} as ranks
  on edges.graph_release_id = ranks.graph_release_id
  and edges.source_domain = ranks.source_domain
