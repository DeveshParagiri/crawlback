from pathlib import Path

from crawlback.config import load_competitor_config, load_extraction_config
from crawlback.motherduck import connect
from crawlback.raw_etl import (
    load_raw_csv_inputs,
    read_domain_ranks_csv,
    read_graph_edges_csv,
    read_wat_evidence_csv,
)


def test_read_graph_edges_csv(tmp_path: Path) -> None:
    path = tmp_path / "graph_edges.csv"
    path.write_text(
        "\n".join(
            [
                "source_domain,target_domain,edge_weight,source_domain_rank_bucket",
                "https://example.com/post,https://www.omni.co/,2,top_100k",
            ]
        ),
        encoding="utf-8",
    )

    rows = read_graph_edges_csv(path)

    assert len(rows) == 1
    assert rows[0].source_domain == "example.com"
    assert rows[0].target_domain == "omni.co"
    assert rows[0].edge_weight == 2


def test_read_domain_ranks_csv_preserves_host_rank(tmp_path: Path) -> None:
    path = tmp_path / "domain_ranks.csv"
    path.write_text(
        "\n".join(
            [
                "rank_entity_type,domain_or_host,rank_position,harmonic_centrality,pagerank,rank_bucket",
                "host,https://blog.hex.tech/post,10,0.5,0.2,top_10k",
            ]
        ),
        encoding="utf-8",
    )

    rows = read_domain_ranks_csv(path, "cc-main-2026-test")

    assert len(rows) == 1
    assert rows[0].domain_or_host == "blog.hex.tech"
    assert rows[0].rank_entity_type == "host"


def test_read_wat_evidence_csv(tmp_path: Path) -> None:
    path = tmp_path / "wat_evidence.csv"
    path.write_text(
        "\n".join(
            [
                (
                    "wat_file_path,warc_record_id,source_url,source_domain,source_host,"
                    "target_url,target_domain,target_company,anchor_text,rel,is_nofollow,"
                    "page_title,page_language,http_status,content_type"
                ),
                (
                    "crawl-data/example.warc.wat.gz,record-1,https://blog.hex.tech/post,"
                    "hex.tech,blog.hex.tech,https://www.omni.co/,omni.co,Omni,Omni,"
                    "nofollow,false,Example,en,200,text/html"
                ),
            ]
        ),
        encoding="utf-8",
    )

    rows = read_wat_evidence_csv(path, "CC-MAIN-2026-01")

    assert len(rows) == 1
    assert rows[0].source_domain == "hex.tech"
    assert rows[0].target_company == "Omni"
    assert rows[0].is_nofollow is True


def test_load_raw_csv_inputs_end_to_end(tmp_path: Path) -> None:
    graph_edges_path = tmp_path / "graph_edges.csv"
    graph_edges_path.write_text(
        "\n".join(
            [
                "source_domain,target_domain,edge_weight,source_domain_rank_bucket",
                "https://example.com/a,https://www.omni.co/,2,top_100k",
                "example.com,omni.co,3,top_10k",
                "irrelevant.com,not-a-competitor.com,1,",
            ]
        ),
        encoding="utf-8",
    )
    domain_ranks_path = tmp_path / "domain_ranks.csv"
    domain_ranks_path.write_text(
        "\n".join(
            [
                "rank_entity_type,domain_or_host,rank_position,harmonic_centrality,pagerank,rank_bucket",
                "domain,example.com,100,0.5,0.2,top_100k",
            ]
        ),
        encoding="utf-8",
    )
    wat_evidence_path = tmp_path / "wat_evidence.csv"
    wat_evidence_path.write_text(
        "\n".join(
            [
                (
                    "wat_file_path,warc_record_id,source_url,source_domain,source_host,"
                    "target_url,target_domain,target_company,anchor_text,rel,is_nofollow,"
                    "page_title,page_language,http_status,content_type"
                ),
                (
                    "crawl-data/example.warc.wat.gz,record-1,https://blog.hex.tech/post,"
                    "hex.tech,blog.hex.tech,https://www.omni.co/,omni.co,Omni,Omni,"
                    "nofollow,false,Example,en,200,text/html"
                ),
            ]
        ),
        encoding="utf-8",
    )

    conn = connect()
    counts = load_raw_csv_inputs(
        conn=conn,
        companies=load_competitor_config(Path("configs/competitors.yml")),
        extraction=load_extraction_config(Path("configs/extraction.yml")),
        graph_edges_path=graph_edges_path,
        domain_ranks_path=domain_ranks_path,
        wat_evidence_path=wat_evidence_path,
    )

    edge_rows = conn.execute(
        """
        select source_domain, target_domain, target_company, edge_weight, source_domain_rank_bucket
        from raw.raw_common_crawl_domain_edges
        """
    ).fetchall()
    rank_rows = conn.execute(
        """
        select domain_or_host, rank_bucket
        from raw.raw_common_crawl_domain_ranks
        """
    ).fetchall()
    evidence_rows = conn.execute(
        """
        select source_domain, target_company, is_nofollow
        from raw.raw_common_crawl_wat_link_evidence
        """
    ).fetchall()

    assert counts.domain_edges == 1
    assert counts.domain_ranks == 1
    assert counts.wat_link_evidence == 1
    assert edge_rows == [("example.com", "omni.co", "Omni", 5, "top_10k")]
    assert rank_rows == [("example.com", "top_100k")]
    assert evidence_rows == [("hex.tech", "Omni", True)]
