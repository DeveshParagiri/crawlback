import csv
from collections.abc import Iterator
from pathlib import Path

import pytest

from crawlback.config import CompetitorConfig
from crawlback.graph_extract import extract_common_crawl_domain_graph, rank_bucket


def test_extract_common_crawl_domain_graph_writes_checkpoints(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lines_by_suffix = {
        "-vertices.txt.gz": [
            "1\tco.omni\t7",
            "2\tcom.tableau\t120",
            "10\tcom.example\t2",
            "11\ttech.hex.blog\t1",
        ],
        "-edges.txt.gz": [
            "10\t1",
            "11\t2",
            "12\t999",
        ],
        "-ranks.txt.gz": [
            "#harmonicc_pos\t#harmonicc_val\t#pr_pos\t#pr_val\t#host_rev\t#n_hosts",
            "50\t200.5\t60\t0.3\tcom.example\t2",
            "200000\t10.5\t300000\t0.01\ttech.hex.blog\t1",
        ],
    }

    def fake_iter_gzip_text_lines(url: str, _timeout_seconds: float) -> Iterator[str]:
        for suffix, lines in lines_by_suffix.items():
            if url.endswith(suffix):
                yield from lines
                return
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(
        "crawlback.graph_extract.iter_gzip_text_lines",
        fake_iter_gzip_text_lines,
    )

    result = extract_common_crawl_domain_graph(
        release_id="cc-main-test",
        companies=CompetitorConfig.model_validate(
            {
                "companies": [
                    {
                        "company": "Omni",
                        "role": "target",
                        "segment": "target",
                        "domains": ["omni.co"],
                    },
                    {
                        "company": "Tableau",
                        "role": "competitor",
                        "segment": "enterprise_incumbent",
                        "domains": ["tableau.com"],
                    },
                ]
            }
        ),
        output_dir=tmp_path,
    )

    assert result.counts.target_vertices == 2
    assert result.counts.scanned_edges == 3
    assert result.counts.filtered_edges == 2
    assert result.counts.source_vertices == 2
    assert result.counts.domain_ranks == 2
    assert result.counts.graph_edges == 2
    assert _read_csv(result.paths.graph_edges) == [
        {
            "source_domain": "example.com",
            "target_domain": "omni.co",
            "edge_weight": "1",
            "source_domain_rank_bucket": "top_10k",
        },
        {
            "source_domain": "blog.hex.tech",
            "target_domain": "tableau.com",
            "edge_weight": "1",
            "source_domain_rank_bucket": "top_1m",
        },
    ]


def test_rank_bucket() -> None:
    assert rank_bucket(10_000) == "top_10k"
    assert rank_bucket(100_000) == "top_100k"
    assert rank_bucket(1_000_000) == "top_1m"
    assert rank_bucket(1_000_001) == "long_tail"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))
