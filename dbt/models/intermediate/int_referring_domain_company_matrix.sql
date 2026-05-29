select
  graph_release_id,
  source_domain,
  max(case when target_company = 'Omni' then 1 else 0 end) = 1 as links_to_omni,
  max(case when target_company = 'Sigma' then 1 else 0 end) = 1 as links_to_sigma,
  max(case when target_company = 'Looker' then 1 else 0 end) = 1 as links_to_looker,
  max(case when target_company = 'ThoughtSpot' then 1 else 0 end) = 1 as links_to_thoughtspot,
  max(case when target_company = 'Hex' then 1 else 0 end) = 1 as links_to_hex,
  max(case when target_company = 'Lightdash' then 1 else 0 end) = 1 as links_to_lightdash,
  max(case when target_company = 'Cube' then 1 else 0 end) = 1 as links_to_cube,
  max(case when target_company = 'Metabase' then 1 else 0 end) = 1 as links_to_metabase,
  max(case when target_company = 'Evidence' then 1 else 0 end) = 1 as links_to_evidence,
  max(case when target_company = 'Rill' then 1 else 0 end) = 1 as links_to_rill,
  max(case when target_company = 'Tableau' then 1 else 0 end) = 1 as links_to_tableau,
  max(case when target_company = 'Mode' then 1 else 0 end) = 1 as links_to_mode,
  count(*) filter (where target_company <> 'Omni') as competitor_count,
  count(*) filter (where target_company <> 'Omni' and target_segment = 'direct_modern_bi') as direct_competitor_count,
  count(*) filter (where target_segment = 'analytics_workspace') as analytics_workspace_competitor_count,
  count(*) filter (where target_segment = 'semantic_layer_adjacent') as semantic_layer_competitor_count,
  count(*) filter (where target_segment = 'oss_self_serve_bi') as oss_self_serve_competitor_count,
  count(*) filter (where target_segment = 'data_app_adjacent') as data_app_competitor_count,
  count(*) filter (where target_segment = 'enterprise_incumbent') as incumbent_competitor_count,
  count(*) filter (where target_segment = 'legacy_acquired') as legacy_acquired_competitor_count,
  string_agg(target_company, ', ' order by target_company) filter (where target_company <> 'Omni') as linked_competitors,
  string_agg(distinct target_segment, ', ' order by target_segment) filter (where target_company <> 'Omni') as competitor_segments,
  sum(total_edge_weight) as total_edge_weight,
  case
    when max(case when source_domain_rank_bucket = 'top_10k' then 1 else 0 end) = 1 then 'top_10k'
    when max(case when source_domain_rank_bucket = 'top_100k' then 1 else 0 end) = 1 then 'top_100k'
    when max(case when source_domain_rank_bucket = 'top_1m' then 1 else 0 end) = 1 then 'top_1m'
    when max(case when source_domain_rank_bucket = 'long_tail' then 1 else 0 end) = 1 then 'long_tail'
    else null
  end as best_rank_bucket,
  max(case when source_high_authority_flag then 1 else 0 end) = 1 as source_high_authority_flag,
  min(source_domain_rank_position) as source_domain_rank_position,
  max(source_domain_harmonic_centrality) as source_domain_harmonic_centrality,
  max(source_domain_pagerank) as source_domain_pagerank
from {{ ref('int_referring_domain_company') }}
group by
  graph_release_id,
  source_domain
