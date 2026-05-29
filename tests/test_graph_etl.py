from pathlib import Path

from crawlback.common_crawl import DomainEdge, DomainVertex
from crawlback.config import load_competitor_config
from crawlback.graph_etl import (
    GraphEdgeInput,
    build_domain_edges,
    graph_edge_inputs_from_common_crawl_edges,
)


def test_graph_edge_inputs_from_common_crawl_edges() -> None:
    inputs = graph_edge_inputs_from_common_crawl_edges(
        edges=[
            DomainEdge(source_node_id=1, target_node_id=2),
            DomainEdge(source_node_id=999, target_node_id=2),
        ],
        source_vertices={
            1: DomainVertex(
                node_id=1,
                reversed_domain="com.example",
                domain="example.com",
                num_hosts=2,
            )
        },
        target_vertices={
            2: DomainVertex(
                node_id=2,
                reversed_domain="co.omni",
                domain="omni.co",
                num_hosts=7,
            )
        },
    )

    assert len(inputs) == 1
    assert inputs[0].source_domain == "example.com"
    assert inputs[0].target_domain == "omni.co"
    assert inputs[0].edge_weight == 1


def test_build_domain_edges_filters_maps_and_deduplicates() -> None:
    companies = load_competitor_config(Path("configs/competitors.yml"))

    edges = build_domain_edges(
        graph_release_id="cc-main-2026-test",
        rows=[
            GraphEdgeInput(
                source_domain="https://example.com/post-1",
                target_domain="https://www.omni.co/",
                edge_weight=2,
                source_domain_rank_bucket="top_100k",
            ),
            GraphEdgeInput(
                source_domain="example.com",
                target_domain="omni.co",
                edge_weight=3,
                source_domain_rank_bucket="top_10k",
            ),
            GraphEdgeInput(
                source_domain="ignored.com",
                target_domain="not-a-competitor.com",
                edge_weight=1,
            ),
        ],
        companies=companies,
        high_authority_rank_buckets={"top_10k", "top_100k"},
    )

    assert len(edges) == 1
    assert edges[0].source_domain == "example.com"
    assert edges[0].target_company == "Omni"
    assert edges[0].target_segment == "target"
    assert edges[0].edge_weight == 5
    assert edges[0].source_domain_rank_bucket == "top_10k"
    assert edges[0].source_high_authority_flag is True
