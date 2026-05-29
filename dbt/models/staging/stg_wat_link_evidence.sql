select
  crawl_id,
  wat_file_path,
  warc_record_id,
  source_url,
  lower(source_domain) as source_domain,
  lower(source_host) as source_host,
  target_url,
  lower(target_domain) as target_domain,
  target_company,
  anchor_text,
  rel,
  is_nofollow,
  page_title,
  page_language,
  http_status,
  content_type,
  extracted_at,
  lower(
    coalesce(source_url, '') || ' ' ||
    coalesce(target_url, '') || ' ' ||
    coalesce(page_title, '') || ' ' ||
    coalesce(anchor_text, '')
  ) as evidence_text
from {{ source('raw', 'raw_common_crawl_wat_link_evidence') }}
