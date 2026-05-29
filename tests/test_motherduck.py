import pytest

from crawlback.models import RawDomainEdge, RawDomainRank, RawWatLinkEvidence
from crawlback.motherduck import (
    connect,
    create_raw_tables,
    insert_domain_edges,
    insert_domain_ranks,
    insert_wat_link_evidence,
)


def test_insert_domain_edges_round_trips() -> None:
    conn = connect()
    create_raw_tables(conn)

    inserted = insert_domain_edges(
        conn,
        [
            RawDomainEdge(
                graph_release_id="cc-main-2026-test",
                source_domain="example.com",
                target_domain="omni.co",
                target_company="Omni",
                target_segment="target",
                edge_weight=2,
                source_domain_rank_bucket="top_100k",
                source_high_authority_flag=True,
            )
        ],
    )

    rows = conn.execute(
        """
        select source_domain, target_domain, target_company, edge_weight
        from raw.raw_common_crawl_domain_edges
        """
    ).fetchall()

    assert inserted == 1
    assert rows == [("example.com", "omni.co", "Omni", 2)]


def test_insert_domain_ranks_round_trips() -> None:
    conn = connect()
    create_raw_tables(conn)

    inserted = insert_domain_ranks(
        conn,
        [
            RawDomainRank(
                graph_release_id="cc-main-2026-test",
                rank_entity_type="domain",
                domain_or_host="example.com",
                rank_position=42,
                harmonic_centrality=0.5,
                pagerank=0.2,
                rank_bucket="top_100k",
            )
        ],
    )

    rows = conn.execute(
        """
        select domain_or_host, rank_entity_type, rank_position, rank_bucket
        from raw.raw_common_crawl_domain_ranks
        """
    ).fetchall()

    assert inserted == 1
    assert rows == [("example.com", "domain", 42, "top_100k")]


def test_insert_wat_link_evidence_round_trips() -> None:
    conn = connect()
    create_raw_tables(conn)

    inserted = insert_wat_link_evidence(
        conn,
        [
            RawWatLinkEvidence(
                crawl_id="CC-MAIN-2026-01",
                wat_file_path="crawl-data/CC-MAIN-2026-01/example.warc.wat.gz",
                warc_record_id="record-1",
                source_url="https://blog.hex.tech/post",
                source_domain="hex.tech",
                source_host="blog.hex.tech",
                target_url="https://www.omni.co/",
                target_domain="omni.co",
                target_company="Omni",
                anchor_text="Omni",
                rel="nofollow",
                page_title="Example",
                page_language="en",
                http_status=200,
                content_type="text/html",
            )
        ],
    )

    rows = conn.execute(
        """
        select source_domain, target_domain, target_company, is_nofollow
        from raw.raw_common_crawl_wat_link_evidence
        """
    ).fetchall()

    assert inserted == 1
    assert rows == [("hex.tech", "omni.co", "Omni", True)]


def test_insert_helpers_return_zero_for_empty_inputs() -> None:
    conn = connect()
    create_raw_tables(conn)

    assert insert_domain_edges(conn, []) == 0
    assert insert_domain_ranks(conn, []) == 0
    assert insert_wat_link_evidence(conn, []) == 0


def test_create_raw_tables_rejects_invalid_schema_name() -> None:
    conn = connect()

    with pytest.raises(ValueError, match="invalid database identifier"):
        create_raw_tables(conn, "raw; drop schema main")
