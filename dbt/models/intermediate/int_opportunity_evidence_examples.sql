with evidence as (
  select
    source_domain,
    source_url,
    target_url,
    target_company,
    anchor_text,
    page_title,
    evidence_text,
    case
      when regexp_matches(
        evidence_text,
        '(bi|analytics|dashboard|semantic layer|dbt|business intelligence|embedded analytics|data app|looker alternative)'
      )
        then 1
      else 0
    end as has_category_term
  from {{ ref('stg_wat_link_evidence') }}
),

ranked as (
  select
    *,
    row_number() over (
      partition by source_domain
      order by has_category_term desc, page_title is not null desc, anchor_text is not null desc
    ) as evidence_row_number
  from evidence
),

aggregated as (
  select
    source_domain,
    count(*) as evidence_record_count,
    sum(has_category_term) as category_match_count,
    max(case when page_title is not null then 1 else 0 end) = 1 as has_page_title,
    max(case when anchor_text is not null then 1 else 0 end) = 1 as has_anchor_text,
    max(case when source_url is not null then 1 else 0 end) = 1 as has_example_url
  from evidence
  group by source_domain
)

select
  aggregated.source_domain,
  aggregated.evidence_record_count,
  aggregated.category_match_count,
  aggregated.has_page_title,
  aggregated.has_anchor_text,
  aggregated.has_example_url,
  ranked.source_url as example_url,
  ranked.target_url as example_target_url,
  ranked.target_company as example_target_company,
  ranked.page_title as example_page_title,
  ranked.anchor_text as example_anchor_text,
  ranked.evidence_text as example_evidence_text
from aggregated
left join ranked
  on aggregated.source_domain = ranked.source_domain
  and ranked.evidence_row_number = 1
