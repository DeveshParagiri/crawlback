"""Common Crawl graph extraction checkpoints.

Streams the large Common Crawl domain graph into small local artifacts for this
project. The raw graph files are never downloaded wholesale. Filtered outputs
under data/ become resumable checkpoints for raw DuckDB or MotherDuck loading.
"""

import csv
import logging
from dataclasses import dataclass
from pathlib import Path

from crawlback.common_crawl import (
    DomainRank,
    DomainVertex,
    domain_graph_files,
    iter_gzip_text_lines,
    parse_domain_rank_line,
    to_reversed_domain_notation,
)
from crawlback.config import CompetitorConfig
from crawlback.normalize_domains import normalize_domain

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class GraphExtractPaths:
    output_dir: Path
    target_vertices: Path
    filtered_edges: Path
    source_vertices: Path
    domain_ranks: Path
    graph_edges: Path


@dataclass(frozen=True)
class GraphExtractCounts:
    target_vertices: int
    scanned_edges: int
    filtered_edges: int
    source_vertices: int
    domain_ranks: int
    graph_edges: int


@dataclass(frozen=True)
class GraphExtractResult:
    paths: GraphExtractPaths
    counts: GraphExtractCounts


def extract_common_crawl_domain_graph(
    release_id: str,
    companies: CompetitorConfig,
    output_dir: Path,
    max_edge_lines: int | None = None,
    max_edge_matches: int | None = None,
    timeout_seconds: float = 60,
    progress_every: int = 10_000_000,
) -> GraphExtractResult:
    paths = _paths(output_dir)
    paths.output_dir.mkdir(parents=True, exist_ok=True)

    company_domains = {domain for company in companies.companies for domain in company.domains}
    if paths.target_vertices.exists():
        target_vertices = _read_vertices_csv(paths.target_vertices)
        LOGGER.info(
            "Reusing %s target vertices from %s", len(target_vertices), paths.target_vertices
        )
    else:
        target_vertices = _extract_target_vertices(
            release_id=release_id,
            domains=company_domains,
            path=paths.target_vertices,
            timeout_seconds=timeout_seconds,
            progress_every=progress_every,
        )
    _ensure_all_targets_found(company_domains, target_vertices)

    scanned_edges, filtered_edges, source_node_ids = _extract_filtered_edges(
        release_id=release_id,
        target_vertices=target_vertices,
        path=paths.filtered_edges,
        max_lines=max_edge_lines,
        max_matches=max_edge_matches,
        timeout_seconds=timeout_seconds,
        progress_every=progress_every,
    )

    source_vertices = _extract_source_vertices(
        release_id=release_id,
        source_node_ids=source_node_ids,
        path=paths.source_vertices,
        timeout_seconds=timeout_seconds,
        progress_every=progress_every,
    )
    domain_ranks = _extract_domain_ranks(
        release_id=release_id,
        domains={vertex.domain for vertex in source_vertices.values()},
        path=paths.domain_ranks,
        timeout_seconds=timeout_seconds,
        progress_every=progress_every,
    )
    graph_edges = _write_graph_edges_csv(
        filtered_edges_path=paths.filtered_edges,
        graph_edges_path=paths.graph_edges,
        source_vertices=source_vertices,
        target_vertices=target_vertices,
        ranks_by_domain=domain_ranks,
    )

    return GraphExtractResult(
        paths=paths,
        counts=GraphExtractCounts(
            target_vertices=len(target_vertices),
            scanned_edges=scanned_edges,
            filtered_edges=filtered_edges,
            source_vertices=len(source_vertices),
            domain_ranks=len(domain_ranks),
            graph_edges=graph_edges,
        ),
    )


def _paths(output_dir: Path) -> GraphExtractPaths:
    return GraphExtractPaths(
        output_dir=output_dir,
        target_vertices=output_dir / "target_vertices.csv",
        filtered_edges=output_dir / "filtered_domain_edges.csv",
        source_vertices=output_dir / "source_vertices.csv",
        domain_ranks=output_dir / "domain_ranks.csv",
        graph_edges=output_dir / "graph_edges.csv",
    )


def _extract_target_vertices(
    release_id: str,
    domains: set[str],
    path: Path,
    timeout_seconds: float,
    progress_every: int,
) -> dict[int, DomainVertex]:
    files = domain_graph_files(release_id)
    wanted = {to_reversed_domain_notation(normalize_domain(domain)) for domain in domains}
    found: dict[int, DomainVertex] = {}

    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["node_id", "domain", "reversed_domain", "num_hosts"],
        )
        writer.writeheader()
        for line_number, line in enumerate(
            iter_gzip_text_lines(files.vertices_url, timeout_seconds),
            start=1,
        ):
            if progress_every > 0 and line_number % progress_every == 0:
                LOGGER.info("Scanned %s target vertices, found %s", line_number, len(found))

            node_id, reversed_domain, num_hosts = _vertex_fields(line)
            if reversed_domain not in wanted:
                continue

            vertex = DomainVertex(
                node_id=node_id,
                reversed_domain=reversed_domain,
                domain=to_domain_notation(reversed_domain),
                num_hosts=num_hosts,
            )
            writer.writerow(_vertex_row(vertex))
            file.flush()
            found[vertex.node_id] = vertex
            LOGGER.info("Found target domain %s at node %s", vertex.domain, vertex.node_id)
            if len(found) == len(wanted):
                break

    return found


def _extract_filtered_edges(
    release_id: str,
    target_vertices: dict[int, DomainVertex],
    path: Path,
    max_lines: int | None,
    max_matches: int | None,
    timeout_seconds: float,
    progress_every: int,
) -> tuple[int, int, set[int]]:
    files = domain_graph_files(release_id)
    source_node_ids: set[int] = set()
    scanned_edges = 0
    filtered_edges = 0

    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["source_node_id", "target_node_id", "target_domain"],
        )
        writer.writeheader()
        for scanned_edges, line in enumerate(
            iter_gzip_text_lines(files.edges_url, timeout_seconds),
            start=1,
        ):
            if max_lines is not None and scanned_edges > max_lines:
                scanned_edges -= 1
                break
            if progress_every > 0 and scanned_edges % progress_every == 0:
                LOGGER.info("Scanned %s domain edges, kept %s", scanned_edges, filtered_edges)

            source_node_id, target_node_id = _edge_fields(line)
            target = target_vertices.get(target_node_id)
            if target is None:
                continue

            filtered_edges += 1
            source_node_ids.add(source_node_id)
            writer.writerow(
                {
                    "source_node_id": source_node_id,
                    "target_node_id": target_node_id,
                    "target_domain": target.domain,
                }
            )
            if max_matches is not None and filtered_edges >= max_matches:
                break

    return scanned_edges, filtered_edges, source_node_ids


def _extract_source_vertices(
    release_id: str,
    source_node_ids: set[int],
    path: Path,
    timeout_seconds: float,
    progress_every: int,
) -> dict[int, DomainVertex]:
    files = domain_graph_files(release_id)
    found: dict[int, DomainVertex] = {}

    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["node_id", "domain", "reversed_domain", "num_hosts"],
        )
        writer.writeheader()
        for line_number, line in enumerate(
            iter_gzip_text_lines(files.vertices_url, timeout_seconds),
            start=1,
        ):
            if progress_every > 0 and line_number % progress_every == 0:
                LOGGER.info("Scanned %s vertices, resolved %s sources", line_number, len(found))

            node_id, reversed_domain, num_hosts = _vertex_fields(line)
            if node_id not in source_node_ids:
                continue

            vertex = DomainVertex(
                node_id=node_id,
                reversed_domain=reversed_domain,
                domain=to_domain_notation(reversed_domain),
                num_hosts=num_hosts,
            )
            found[vertex.node_id] = vertex
            writer.writerow(_vertex_row(vertex))
            if len(found) == len(source_node_ids):
                break

    return found


def _extract_domain_ranks(
    release_id: str,
    domains: set[str],
    path: Path,
    timeout_seconds: float,
    progress_every: int,
) -> dict[str, DomainRank]:
    files = domain_graph_files(release_id)
    wanted = {to_reversed_domain_notation(domain) for domain in domains}
    found: dict[str, DomainRank] = {}

    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "rank_entity_type",
                "domain_or_host",
                "rank_position",
                "harmonic_centrality",
                "pagerank",
                "rank_bucket",
            ],
        )
        writer.writeheader()
        for line_number, line in enumerate(
            iter_gzip_text_lines(files.ranks_url, timeout_seconds),
            start=1,
        ):
            if progress_every > 0 and line_number % progress_every == 0:
                LOGGER.info("Scanned %s ranks, resolved %s source ranks", line_number, len(found))

            if line.startswith("#"):
                continue

            reversed_domain = _rank_reversed_domain(line)
            if reversed_domain not in wanted:
                continue

            rank = parse_domain_rank_line(line)
            if rank is None:
                continue

            found[rank.domain] = rank
            writer.writerow(
                {
                    "rank_entity_type": "domain",
                    "domain_or_host": rank.domain,
                    "rank_position": rank.harmonicc_position,
                    "harmonic_centrality": rank.harmonicc_value,
                    "pagerank": rank.pagerank,
                    "rank_bucket": rank_bucket(rank.harmonicc_position),
                }
            )
            if len(found) == len(wanted):
                break

    return found


def _write_graph_edges_csv(
    filtered_edges_path: Path,
    graph_edges_path: Path,
    source_vertices: dict[int, DomainVertex],
    target_vertices: dict[int, DomainVertex],
    ranks_by_domain: dict[str, DomainRank],
) -> int:
    rows_written = 0
    with (
        filtered_edges_path.open("r", encoding="utf-8", newline="") as input_file,
        graph_edges_path.open("w", encoding="utf-8", newline="") as output_file,
    ):
        reader = csv.DictReader(input_file)
        writer = csv.DictWriter(
            output_file,
            fieldnames=[
                "source_domain",
                "target_domain",
                "edge_weight",
                "source_domain_rank_bucket",
            ],
        )
        writer.writeheader()
        for row in reader:
            source = source_vertices.get(int(row["source_node_id"]))
            target = target_vertices.get(int(row["target_node_id"]))
            if source is None or target is None:
                continue

            rank = ranks_by_domain.get(source.domain)
            writer.writerow(
                {
                    "source_domain": source.domain,
                    "target_domain": target.domain,
                    "edge_weight": 1,
                    "source_domain_rank_bucket": (
                        rank_bucket(rank.harmonicc_position) if rank is not None else None
                    ),
                }
            )
            rows_written += 1

    return rows_written


def rank_bucket(rank_position: int) -> str:
    if rank_position <= 10_000:
        return "top_10k"
    if rank_position <= 100_000:
        return "top_100k"
    if rank_position <= 1_000_000:
        return "top_1m"
    return "long_tail"


def to_domain_notation(value: str) -> str:
    return ".".join(reversed(value.split(".")))


def _vertex_fields(line: str) -> tuple[int, str, int]:
    parts = line.split("\t")
    if len(parts) != 3:
        raise ValueError(f"expected vertex line with 3 tab-separated fields, got {line!r}")
    return int(parts[0]), parts[1], int(parts[2])


def _edge_fields(line: str) -> tuple[int, int]:
    parts = line.split("\t")
    if len(parts) != 2:
        raise ValueError(f"expected edge line with 2 tab-separated fields, got {line!r}")
    return int(parts[0]), int(parts[1])


def _rank_reversed_domain(line: str) -> str:
    parts = line.split("\t")
    if len(parts) != 6:
        raise ValueError(f"expected rank line with 6 tab-separated fields, got {line!r}")
    return parts[4]


def _ensure_all_targets_found(domains: set[str], target_vertices: dict[int, DomainVertex]) -> None:
    found_domains = {vertex.domain for vertex in target_vertices.values()}
    missing = sorted({normalize_domain(domain) for domain in domains} - found_domains)
    if missing:
        raise ValueError(f"target domains missing from Common Crawl vertices: {missing}")


def _vertex_row(vertex: DomainVertex) -> dict[str, int | str]:
    return {
        "node_id": vertex.node_id,
        "domain": vertex.domain,
        "reversed_domain": vertex.reversed_domain,
        "num_hosts": vertex.num_hosts,
    }


def _read_vertices_csv(path: Path) -> dict[int, DomainVertex]:
    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        return {
            int(row["node_id"]): DomainVertex(
                node_id=int(row["node_id"]),
                domain=row["domain"],
                reversed_domain=row["reversed_domain"],
                num_hosts=int(row["num_hosts"]),
            )
            for row in reader
        }
