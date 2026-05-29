with raw_edges as (
  select
    graph_release_id,
    lower(source_domain) as source_domain,
    lower(target_domain) as target_domain,
    target_company,
    target_segment,
    coalesce(edge_weight, 1) as edge_weight,
    source_domain_rank_bucket,
    source_high_authority_flag,
    loaded_at
  from {{ source('raw', 'raw_common_crawl_domain_edges') }}
),

deduped as (
  select
    graph_release_id,
    source_domain,
    target_company,
    target_segment,
    string_agg(distinct target_domain, ', ') as target_domains,
    count(*) as raw_edge_rows,
    sum(edge_weight) as total_edge_weight,
    case
      when max(case when source_domain_rank_bucket = 'top_10k' then 1 else 0 end) = 1 then 'top_10k'
      when max(case when source_domain_rank_bucket = 'top_100k' then 1 else 0 end) = 1 then 'top_100k'
      when max(case when source_domain_rank_bucket = 'top_1m' then 1 else 0 end) = 1 then 'top_1m'
      when max(case when source_domain_rank_bucket = 'long_tail' then 1 else 0 end) = 1 then 'long_tail'
      else null
    end as source_domain_rank_bucket,
    max(case when source_high_authority_flag then 1 else 0 end) = 1 as source_high_authority_flag,
    max(loaded_at) as loaded_at
  from raw_edges
  group by
    graph_release_id,
    source_domain,
    target_company,
    target_segment
)

select * from deduped
