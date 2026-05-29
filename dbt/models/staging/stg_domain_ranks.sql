with ranked as (
  select
    graph_release_id,
    rank_entity_type,
    lower(domain_or_host) as domain_or_host,
    rank_position,
    harmonic_centrality,
    pagerank,
    rank_bucket,
    loaded_at,
    row_number() over (
      partition by graph_release_id, rank_entity_type, lower(domain_or_host)
      order by rank_position nulls last, loaded_at desc
    ) as rank_row_number
  from {{ source('raw', 'raw_common_crawl_domain_ranks') }}
)

select
  graph_release_id,
  rank_entity_type,
  domain_or_host,
  rank_position,
  harmonic_centrality,
  pagerank,
  rank_bucket,
  loaded_at
from ranked
where rank_row_number = 1
