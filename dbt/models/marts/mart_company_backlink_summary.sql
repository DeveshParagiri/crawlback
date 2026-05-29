with company_releases as (
  select
    releases.graph_release_id,
    companies.company as target_company,
    companies.role,
    companies.segment as target_segment
  from (select distinct graph_release_id from {{ ref('int_referring_domain_company') }}) as releases
  cross join {{ ref('dim_companies') }} as companies
),

counts as (
  select
    graph_release_id,
    target_company,
    count(distinct source_domain) as referring_domain_count,
    count(distinct source_domain) filter (
      where source_high_authority_flag
    ) as high_authority_referring_domain_count,
    sum(total_edge_weight) as total_edge_weight
  from {{ ref('int_referring_domain_company') }}
  group by
    graph_release_id,
    target_company
),

filled as (
  select
    company_releases.graph_release_id,
    company_releases.target_company,
    company_releases.role,
    company_releases.target_segment,
    coalesce(counts.referring_domain_count, 0) as referring_domain_count,
    coalesce(counts.high_authority_referring_domain_count, 0) as high_authority_referring_domain_count,
    coalesce(counts.total_edge_weight, 0) as total_edge_weight
  from company_releases
  left join counts
    on company_releases.graph_release_id = counts.graph_release_id
    and company_releases.target_company = counts.target_company
),

scored as (
  select
    *,
    referring_domain_count::double
      / nullif(max(referring_domain_count) over (partition by graph_release_id), 0)
      as normalized_referring_domain_count,
    high_authority_referring_domain_count::double
      / nullif(max(high_authority_referring_domain_count) over (partition by graph_release_id), 0)
      as normalized_high_authority_referring_domain_count,
    total_edge_weight::double
      / nullif(max(total_edge_weight) over (partition by graph_release_id), 0)
      as normalized_edge_depth
  from filled
)

select
  graph_release_id,
  target_company,
  role,
  target_segment,
  referring_domain_count,
  high_authority_referring_domain_count,
  total_edge_weight,
  coalesce(normalized_referring_domain_count, 0) as normalized_referring_domain_count,
  coalesce(normalized_high_authority_referring_domain_count, 0)
    as normalized_high_authority_referring_domain_count,
  coalesce(normalized_edge_depth, 0) as normalized_edge_depth,
  round(
    45 * coalesce(normalized_referring_domain_count, 0)
    + 35 * coalesce(normalized_high_authority_referring_domain_count, 0)
    + 20 * coalesce(normalized_edge_depth, 0),
    2
  ) as backlink_strength_proxy
from scored
