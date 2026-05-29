import gzip
import io
from urllib.request import Request

import pytest

from crawlback import common_crawl
from crawlback.common_crawl import (
    domain_graph_files,
    fetch_domain_edges_for_targets,
    fetch_domain_vertex_sample,
    fetch_domain_vertices_for_domains,
    fetch_vertices_by_node_id,
    fetch_web_graph_releases,
    latest_web_graph_release,
    parse_domain_edge_line,
    parse_domain_rank_line,
    parse_domain_vertex_line,
    parse_stats_text,
    reverse_domain_notation,
    to_reversed_domain_notation,
)


class FakeResponse(io.BytesIO):
    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


def test_fetch_web_graph_releases_from_graphinfo(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = b"""
    [
      {
        "id": "cc-main-2026-feb-mar-apr",
        "crawls": ["CC-MAIN-2026-08", "CC-MAIN-2026-12", "CC-MAIN-2026-17"],
        "index": "https://data.commoncrawl.org/projects/hyperlinkgraph/cc-main-2026-feb-mar-apr/index.html",
        "location": "s3://commoncrawl/projects/hyperlinkgraph/cc-main-2026-feb-mar-apr/",
        "stats": {
          "host": {"nodes": 268996919, "arcs": 9422229117},
          "domain": {"nodes": 124646710, "arcs": 4756191406}
        }
      }
    ]
    """

    def fake_urlopen(request: Request, timeout: float) -> FakeResponse:
        assert request.full_url == "https://index.commoncrawl.org/graphinfo.json"
        assert timeout == 30
        return FakeResponse(payload)

    monkeypatch.setattr(common_crawl, "urlopen", fake_urlopen)

    releases = fetch_web_graph_releases()

    assert len(releases) == 1
    assert latest_web_graph_release().id == "cc-main-2026-feb-mar-apr"
    assert releases[0].stats.domain.arcs == 4_756_191_406


def test_domain_graph_files_are_deterministic() -> None:
    files = domain_graph_files("cc-main-2026-feb-mar-apr")

    assert files.vertices_url.endswith(
        "/cc-main-2026-feb-mar-apr/domain/cc-main-2026-feb-mar-apr-domain-vertices.txt.gz"
    )
    assert files.edges_url.endswith(
        "/cc-main-2026-feb-mar-apr/domain/cc-main-2026-feb-mar-apr-domain-edges.txt.gz"
    )
    assert files.ranks_url.endswith(
        "/cc-main-2026-feb-mar-apr/domain/cc-main-2026-feb-mar-apr-domain-ranks.txt.gz"
    )
    assert files.stats_url.endswith(
        "/cc-main-2026-feb-mar-apr/domain/cc-main-2026-feb-mar-apr-domain.stats"
    )


def test_fetch_domain_vertex_sample_streams_bounded_gzip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    compressed = gzip.compress(b"0\tco.omni\t1\n1\tcom.tableau\t3\n")

    def fake_urlopen(request: Request, timeout: float) -> FakeResponse:
        assert request.full_url.endswith("-domain-vertices.txt.gz")
        assert timeout == 30
        return FakeResponse(compressed)

    monkeypatch.setattr(common_crawl, "urlopen", fake_urlopen)

    sample = fetch_domain_vertex_sample("cc-main-2026-feb-mar-apr", max_lines=2)

    assert [row.domain for row in sample] == ["omni.co", "tableau.com"]
    assert [row.num_hosts for row in sample] == [1, 3]


def test_fetch_domain_vertices_for_domains(monkeypatch: pytest.MonkeyPatch) -> None:
    compressed = gzip.compress(b"0\tco.omni\t1\n1\tcom.example\t2\n2\tcom.tableau\t3\n")

    def fake_urlopen(request: Request, timeout: float) -> FakeResponse:
        assert request.full_url.endswith("-domain-vertices.txt.gz")
        assert timeout == 30
        return FakeResponse(compressed)

    monkeypatch.setattr(common_crawl, "urlopen", fake_urlopen)

    vertices = fetch_domain_vertices_for_domains(
        "cc-main-2026-feb-mar-apr",
        {"https://www.omni.co/", "tableau.com"},
    )

    assert set(vertices) == {"omni.co", "tableau.com"}
    assert vertices["omni.co"].node_id == 0
    assert vertices["tableau.com"].node_id == 2


def test_fetch_domain_edges_for_targets(monkeypatch: pytest.MonkeyPatch) -> None:
    compressed = gzip.compress(b"10\t1\n20\t2\n30\t3\n")

    def fake_urlopen(request: Request, timeout: float) -> FakeResponse:
        assert request.full_url.endswith("-domain-edges.txt.gz")
        assert timeout == 30
        return FakeResponse(compressed)

    monkeypatch.setattr(common_crawl, "urlopen", fake_urlopen)

    edges = fetch_domain_edges_for_targets(
        "cc-main-2026-feb-mar-apr",
        target_node_ids={2, 3},
        max_matches=1,
    )

    assert len(edges) == 1
    assert edges[0].source_node_id == 20
    assert edges[0].target_node_id == 2


def test_fetch_vertices_by_node_id(monkeypatch: pytest.MonkeyPatch) -> None:
    compressed = gzip.compress(b"0\tco.omni\t1\n1\tcom.example\t2\n2\tcom.tableau\t3\n")

    def fake_urlopen(request: Request, timeout: float) -> FakeResponse:
        assert request.full_url.endswith("-domain-vertices.txt.gz")
        assert timeout == 30
        return FakeResponse(compressed)

    monkeypatch.setattr(common_crawl, "urlopen", fake_urlopen)

    vertices = fetch_vertices_by_node_id("cc-main-2026-feb-mar-apr", {1, 2})

    assert vertices[1].domain == "example.com"
    assert vertices[2].domain == "tableau.com"


def test_fetch_gzip_text_lines_rejects_non_positive_limits() -> None:
    with pytest.raises(ValueError, match="max_lines must be positive"):
        common_crawl.fetch_gzip_text_lines("https://example.com/file.gz", max_lines=0)


def test_parse_domain_vertex_line() -> None:
    vertex = parse_domain_vertex_line("42\tco.omni\t7")

    assert vertex.node_id == 42
    assert vertex.reversed_domain == "co.omni"
    assert vertex.domain == "omni.co"
    assert vertex.num_hosts == 7


def test_parse_domain_edge_line() -> None:
    edge = parse_domain_edge_line("42\t900")

    assert edge.source_node_id == 42
    assert edge.target_node_id == 900


def test_parse_domain_rank_line() -> None:
    rank = parse_domain_rank_line("7\t123.5\t9\t0.5\tcom.tableau\t120")

    assert rank is not None
    assert rank.harmonicc_position == 7
    assert rank.harmonicc_value == 123.5
    assert rank.pagerank_position == 9
    assert rank.pagerank == 0.5
    assert rank.domain == "tableau.com"
    assert rank.num_hosts == 120


def test_parse_domain_rank_line_skips_header() -> None:
    assert parse_domain_rank_line("#harmonicc_pos\t#harmonicc_val") is None


def test_reverse_domain_notation() -> None:
    assert reverse_domain_notation("com.example.blog") == "blog.example.com"


def test_to_reversed_domain_notation() -> None:
    assert to_reversed_domain_notation("blog.example.com") == "com.example.blog"


def test_parse_stats_text() -> None:
    stats = parse_stats_text("nodes=124646710\npercdangling=65.24\nname=value\n")

    assert stats == {"nodes": 124646710, "percdangling": 65.24, "name": "value"}
