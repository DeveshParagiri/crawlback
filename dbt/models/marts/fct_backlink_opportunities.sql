with opportunities as (
  select *
  from {{ ref('int_referring_domain_company_matrix') }}
  where competitor_count > 0
    and links_to_omni = false
),

enriched as (
  select
    opportunities.*,
    coalesce(evidence.evidence_record_count, 0) as evidence_record_count,
    coalesce(evidence.category_match_count, 0) as category_match_count,
    coalesce(evidence.has_page_title, false) as has_page_title,
    coalesce(evidence.has_anchor_text, false) as has_anchor_text,
    coalesce(evidence.has_example_url, false) as has_example_url,
    evidence.example_url,
    evidence.example_target_url,
    evidence.example_target_company,
    evidence.example_page_title,
    evidence.example_anchor_text,
    evidence.example_evidence_text
  from opportunities
  left join {{ ref('int_opportunity_evidence_examples') }} as evidence
    on opportunities.source_domain = evidence.source_domain
),

signals as (
  select
    *,
    least(competitor_count::double / 4.0, 1.0) as competitor_coverage_signal,
    case best_rank_bucket
      when 'top_10k' then 1.0
      when 'top_100k' then 0.85
      when 'top_1m' then 0.45
      when 'long_tail' then 0.15
      else 0.0
    end as authority_signal,
    case
      when links_to_sigma or links_to_hex or links_to_lightdash or links_to_cube then 1.0
      when links_to_looker and direct_competitor_count > 0 then 0.85
      when direct_competitor_count > 0
        or analytics_workspace_competitor_count > 0
        or semantic_layer_competitor_count > 0 then 0.75
      when oss_self_serve_competitor_count > 0 or data_app_competitor_count > 0 then 0.5
      when incumbent_competitor_count > 0 or legacy_acquired_competitor_count > 0 then 0.25
      else 0.0
    end as segment_relevance_signal,
    least(category_match_count::double / 2.0, 1.0) as category_relevance_signal,
    case
      when evidence_record_count = 0 then 0.0
      else least(
        0.4
        + case when has_example_url then 0.2 else 0 end
        + case when has_page_title then 0.2 else 0 end
        + case when has_anchor_text then 0.2 else 0 end,
        1.0
      )
    end as evidence_quality_signal,
    case
      when source_domain in ('bit.ly', 't.co', 'tinyurl.com', 'goo.gl', 'ow.ly') then 0.0
      when regexp_matches(source_domain, '(casino|coupon|viagra|porn|xxx|apk|crack|warez|torrent)') then 0.0
      when length(source_domain) > 80 then 0.4
      else 1.0
    end as clean_domain_signal
  from enriched
),

scored as (
  select
    *,
    round(
      30 * competitor_coverage_signal
      + 25 * authority_signal
      + 15 * segment_relevance_signal
      + 15 * category_relevance_signal
      + 10 * evidence_quality_signal
      + 5 * clean_domain_signal,
      2
    ) as opportunity_score
  from signals
)

select
  graph_release_id,
  source_domain as opportunity_domain,
  false as links_to_omni,
  linked_competitors,
  competitor_segments,
  competitor_count,
  direct_competitor_count,
  analytics_workspace_competitor_count,
  semantic_layer_competitor_count,
  oss_self_serve_competitor_count,
  data_app_competitor_count,
  incumbent_competitor_count,
  legacy_acquired_competitor_count,
  best_rank_bucket as source_domain_rank_bucket,
  source_high_authority_flag,
  source_domain_rank_position,
  source_domain_harmonic_centrality,
  source_domain_pagerank,
  total_edge_weight,
  competitor_coverage_signal,
  authority_signal,
  segment_relevance_signal,
  category_relevance_signal,
  evidence_quality_signal,
  clean_domain_signal,
  opportunity_score,
  case
    when opportunity_score >= 75 then 'tier_1'
    when opportunity_score >= 50 then 'tier_2'
    when opportunity_score >= 25 then 'tier_3'
    else 'monitor'
  end as opportunity_tier,
  example_url,
  example_target_url,
  example_target_company,
  example_page_title,
  example_anchor_text,
  case
    when example_evidence_text is not null
      and regexp_matches(example_evidence_text, '(alternative|vs|compare|comparison)')
      then 'Create comparison content'
    when example_evidence_text is not null
      and regexp_matches(example_evidence_text, '(partner|integration|marketplace|ecosystem)')
      then 'Partner/integration outreach'
    when example_evidence_text is not null
      and regexp_matches(example_evidence_text, '(blog|newsletter|article|post|community)')
      then 'Community/content outreach'
    when source_high_authority_flag and evidence_record_count = 0 then 'Validate with SEO tool'
    else 'Review manually'
  end as recommended_action,
  concat(
    'Links to ',
    competitor_count::varchar,
    ' competitor(s): ',
    coalesce(linked_competitors, 'none'),
    '. Rank bucket: ',
    coalesce(best_rank_bucket, 'unknown'),
    '. WAT evidence rows: ',
    evidence_record_count::varchar,
    '.'
  ) as score_explanation
from scored
