with releases as (
  select distinct graph_release_id
  from {{ ref('int_referring_domain_company') }}
),

competitors as (
  select company as competitor_company, segment as competitor_segment
  from {{ ref('stg_companies') }}
  where role = 'competitor'
),

release_competitors as (
  select
    releases.graph_release_id,
    competitors.competitor_company,
    competitors.competitor_segment
  from releases
  cross join competitors
),

omni_domains as (
  select distinct
    graph_release_id,
    source_domain
  from {{ ref('int_referring_domain_company') }}
  where target_company = 'Omni'
),

omni_counts as (
  select
    graph_release_id,
    count(*) as omni_referring_domain_count
  from omni_domains
  group by graph_release_id
),

competitor_domains as (
  select distinct
    graph_release_id,
    target_company as competitor_company,
    source_domain
  from {{ ref('int_referring_domain_company') }}
  where target_company <> 'Omni'
),

overlap_counts as (
  select
    release_competitors.graph_release_id,
    release_competitors.competitor_company,
    release_competitors.competitor_segment,
    count(competitor_domains.source_domain) as competitor_referring_domain_count,
    count(competitor_domains.source_domain) filter (
      where omni_domains.source_domain is not null
    ) as overlap_domain_count,
    count(competitor_domains.source_domain) filter (
      where omni_domains.source_domain is null
    ) as competitor_only_domain_count
  from release_competitors
  left join competitor_domains
    on release_competitors.graph_release_id = competitor_domains.graph_release_id
    and release_competitors.competitor_company = competitor_domains.competitor_company
  left join omni_domains
    on competitor_domains.graph_release_id = omni_domains.graph_release_id
    and competitor_domains.source_domain = omni_domains.source_domain
  group by
    release_competitors.graph_release_id,
    release_competitors.competitor_company,
    release_competitors.competitor_segment
)

select
  overlap_counts.graph_release_id,
  overlap_counts.competitor_company,
  overlap_counts.competitor_segment,
  overlap_counts.competitor_referring_domain_count,
  coalesce(omni_counts.omni_referring_domain_count, 0) as omni_referring_domain_count,
  overlap_counts.overlap_domain_count,
  overlap_counts.competitor_only_domain_count,
  coalesce(omni_counts.omni_referring_domain_count, 0) - overlap_counts.overlap_domain_count
    as omni_only_domain_count,
  overlap_counts.competitor_referring_domain_count
    + coalesce(omni_counts.omni_referring_domain_count, 0)
    - overlap_counts.overlap_domain_count as union_domain_count,
  case
    when overlap_counts.competitor_referring_domain_count
      + coalesce(omni_counts.omni_referring_domain_count, 0)
      - overlap_counts.overlap_domain_count = 0
      then 0
    else overlap_counts.overlap_domain_count::double
      / (
        overlap_counts.competitor_referring_domain_count
        + coalesce(omni_counts.omni_referring_domain_count, 0)
        - overlap_counts.overlap_domain_count
      )
  end as jaccard_overlap
from overlap_counts
left join omni_counts
  on overlap_counts.graph_release_id = omni_counts.graph_release_id
