import pytest
from pydantic import ValidationError

from crawlback.models import RawDomainEdge, RawDomainRank, RawWatLinkEvidence


def test_raw_domain_edge_normalizes_domains() -> None:
    edge = RawDomainEdge(
        graph_release_id="cc-main-2026-test",
        source_domain="https://Blog.Hex.Tech/post",
        target_domain="WWW.OMNI.CO",
        target_company="Omni",
        target_segment="target",
        edge_weight=3,
    )

    assert edge.source_domain == "hex.tech"
    assert edge.target_domain == "omni.co"


def test_raw_domain_edge_rejects_negative_weight() -> None:
    with pytest.raises(ValidationError):
        RawDomainEdge(
            graph_release_id="cc-main-2026-test",
            source_domain="hex.tech",
            target_domain="omni.co",
            target_company="Omni",
            target_segment="target",
            edge_weight=-1,
        )


def test_raw_domain_rank_normalizes_entity() -> None:
    rank = RawDomainRank(
        graph_release_id="cc-main-2026-test",
        rank_entity_type="domain",
        domain_or_host="https://www.tableau.com/products",
        rank_position=100,
        rank_bucket="top_10k",
    )

    assert rank.domain_or_host == "tableau.com"


def test_raw_domain_rank_preserves_host_entity() -> None:
    rank = RawDomainRank(
        graph_release_id="cc-main-2026-test",
        rank_entity_type="host",
        domain_or_host="https://blog.hex.tech/posts",
        rank_position=100,
        rank_bucket="top_10k",
    )

    assert rank.domain_or_host == "blog.hex.tech"


def test_raw_wat_link_evidence_normalizes_and_sets_nofollow() -> None:
    evidence = RawWatLinkEvidence(
        crawl_id="CC-MAIN-2026-01",
        wat_file_path="crawl-data/CC-MAIN-2026-01/example.warc.wat.gz",
        source_url="https://blog.hex.tech/post",
        source_domain="hex.tech",
        source_host="BLOG.HEX.TECH",
        target_url="https://www.omni.co/",
        target_domain="omni.co",
        target_company="Omni",
        anchor_text=" Omni ",
        rel="noopener nofollow",
        http_status=200,
    )

    assert evidence.source_host == "blog.hex.tech"
    assert evidence.anchor_text == "Omni"
    assert evidence.is_nofollow is True


def test_raw_wat_link_evidence_rejects_domain_mismatch() -> None:
    with pytest.raises(ValidationError):
        RawWatLinkEvidence(
            crawl_id="CC-MAIN-2026-01",
            wat_file_path="crawl-data/CC-MAIN-2026-01/example.warc.wat.gz",
            source_url="https://blog.hex.tech/post",
            source_domain="example.com",
            source_host="blog.hex.tech",
            target_url="https://www.omni.co/",
            target_domain="omni.co",
            target_company="Omni",
        )
