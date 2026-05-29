"""Local raw ETL orchestration.

Wires local CSV inputs into the raw loading contract for tests, development, and
small reproducible samples. Exercises the same validation, graph mapping, and
DuckDB loading path that real Common Crawl extraction will use later.
"""

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import duckdb

from crawlback.config import CompetitorConfig, ExtractionConfig
from crawlback.graph_etl import GraphEdgeInput, build_domain_edges
from crawlback.models import RawDomainRank, RawWatLinkEvidence
from crawlback.motherduck import (
    create_raw_tables,
    insert_domain_edges,
    insert_domain_ranks,
    insert_wat_link_evidence,
)


@dataclass(frozen=True)
class RawLoadCounts:
    domain_edges: int
    domain_ranks: int
    wat_link_evidence: int


def load_raw_csv_inputs(
    conn: duckdb.DuckDBPyConnection,
    companies: CompetitorConfig,
    extraction: ExtractionConfig,
    graph_edges_path: Path,
    domain_ranks_path: Path | None = None,
    wat_evidence_path: Path | None = None,
    schema: str = "raw",
) -> RawLoadCounts:
    create_raw_tables(conn, schema=schema)

    graph_edges = build_domain_edges(
        graph_release_id=extraction.graph_release_id,
        rows=read_graph_edges_csv(graph_edges_path),
        companies=companies,
        high_authority_rank_buckets=set(extraction.high_authority_rank_buckets),
    )
    domain_edge_count = insert_domain_edges(conn, graph_edges, schema=schema)

    domain_rank_count = 0
    if domain_ranks_path is not None:
        domain_rank_count = insert_domain_ranks(
            conn,
            read_domain_ranks_csv(domain_ranks_path, extraction.graph_release_id),
            schema=schema,
        )

    wat_evidence_count = 0
    if wat_evidence_path is not None:
        wat_evidence_count = insert_wat_link_evidence(
            conn,
            read_wat_evidence_csv(wat_evidence_path, extraction.crawl_id),
            schema=schema,
        )

    return RawLoadCounts(
        domain_edges=domain_edge_count,
        domain_ranks=domain_rank_count,
        wat_link_evidence=wat_evidence_count,
    )


def read_graph_edges_csv(path: Path) -> list[GraphEdgeInput]:
    return [
        GraphEdgeInput(
            source_domain=row["source_domain"],
            target_domain=row["target_domain"],
            edge_weight=_optional_int(row.get("edge_weight")),
            source_domain_rank_bucket=_optional_str(row.get("source_domain_rank_bucket")),
        )
        for row in _read_csv(path)
    ]


def read_domain_ranks_csv(path: Path, graph_release_id: str) -> list[RawDomainRank]:
    return [
        RawDomainRank(
            graph_release_id=graph_release_id,
            rank_entity_type=_rank_entity_type(row["rank_entity_type"]),
            domain_or_host=row["domain_or_host"],
            rank_position=_optional_int(row.get("rank_position")),
            harmonic_centrality=_optional_float(row.get("harmonic_centrality")),
            pagerank=_optional_float(row.get("pagerank")),
            rank_bucket=_optional_str(row.get("rank_bucket")),
        )
        for row in _read_csv(path)
    ]


def read_wat_evidence_csv(path: Path, crawl_id: str) -> list[RawWatLinkEvidence]:
    return [
        RawWatLinkEvidence(
            crawl_id=crawl_id,
            wat_file_path=row["wat_file_path"],
            warc_record_id=_optional_str(row.get("warc_record_id")),
            source_url=row["source_url"],
            source_domain=row["source_domain"],
            source_host=row["source_host"],
            target_url=row["target_url"],
            target_domain=row["target_domain"],
            target_company=row["target_company"],
            anchor_text=_optional_str(row.get("anchor_text")),
            rel=_optional_str(row.get("rel")),
            is_nofollow=_optional_bool(row.get("is_nofollow")),
            page_title=_optional_str(row.get("page_title")),
            page_language=_optional_str(row.get("page_language")),
            http_status=_optional_int(row.get("http_status")),
            content_type=_optional_str(row.get("content_type")),
        )
        for row in _read_csv(path)
    ]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def _optional_str(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None


def _optional_int(value: str | None) -> int | None:
    text = _optional_str(value)
    if text is None:
        return None
    return int(text)


def _optional_float(value: str | None) -> float | None:
    text = _optional_str(value)
    if text is None:
        return None
    return float(text)


def _optional_bool(value: str | None) -> bool:
    text = _optional_str(value)
    if text is None:
        return False
    return text.lower() in {"1", "true", "t", "yes", "y"}


def _rank_entity_type(value: str) -> Literal["domain", "host"]:
    if value == "domain":
        return "domain"
    if value == "host":
        return "host"
    raise ValueError(f"rank_entity_type must be domain or host, got {value!r}")
