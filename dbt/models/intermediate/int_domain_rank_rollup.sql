select
  graph_release_id,
  domain_or_host as source_domain,
  min(rank_position) as best_rank_position,
  max(harmonic_centrality) as harmonic_centrality,
  max(pagerank) as pagerank,
  case
    when min(case when rank_bucket = 'top_10k' then 1 else 99 end) = 1 then 'top_10k'
    when min(case when rank_bucket = 'top_100k' then 2 else 99 end) = 2 then 'top_100k'
    when min(case when rank_bucket = 'top_1m' then 3 else 99 end) = 3 then 'top_1m'
    when min(case when rank_bucket = 'long_tail' then 4 else 99 end) = 4 then 'long_tail'
    else null
  end as best_rank_bucket,
  min(rank_position) <= 100000 as high_authority_rank_flag
from {{ ref('stg_domain_ranks') }}
where rank_entity_type = 'domain'
group by
  graph_release_id,
  domain_or_host
