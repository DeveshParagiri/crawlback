"""Common Crawl Web Graph access helpers.

The only code that reaches Common Crawl directly. Discovers graph releases,
builds release file URLs, reads release stats, and streams bounded samples from
compressed graph files for the ETL layer.
"""

import gzip
import json
from collections.abc import Iterator, Mapping
from itertools import islice
from typing import Any
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from crawlback.normalize_domains import normalize_domain

GRAPHINFO_URL = "https://index.commoncrawl.org/graphinfo.json"
DATA_BASE_URL = "https://data.commoncrawl.org/projects/hyperlinkgraph"
USER_AGENT = "crawlback/0.1"


class GraphStats(BaseModel):
    model_config = ConfigDict(frozen=True)

    nodes: int = Field(ge=0)
    arcs: int = Field(ge=0)


class ReleaseStats(BaseModel):
    model_config = ConfigDict(frozen=True)

    host: GraphStats
    domain: GraphStats


class WebGraphRelease(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    crawls: tuple[str, ...] = Field(min_length=1)
    index: HttpUrl
    location: str = Field(min_length=1)
    stats: ReleaseStats


class DomainGraphFiles(BaseModel):
    model_config = ConfigDict(frozen=True)

    vertices_url: str
    edges_url: str
    ranks_url: str
    stats_url: str


class DomainVertex(BaseModel):
    model_config = ConfigDict(frozen=True)

    node_id: int = Field(ge=0)
    reversed_domain: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    num_hosts: int = Field(ge=0)


class DomainEdge(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_node_id: int = Field(ge=0)
    target_node_id: int = Field(ge=0)


class DomainRank(BaseModel):
    model_config = ConfigDict(frozen=True)

    harmonicc_position: int = Field(ge=1)
    harmonicc_value: float = Field(ge=0)
    pagerank_position: int = Field(ge=1)
    pagerank: float = Field(ge=0)
    reversed_domain: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    num_hosts: int = Field(ge=0)


def fetch_web_graph_releases(
    graphinfo_url: str = GRAPHINFO_URL,
    timeout_seconds: float = 30,
) -> list[WebGraphRelease]:
    payload = _fetch_json(graphinfo_url, timeout_seconds)
    if not isinstance(payload, list):
        raise ValueError("Common Crawl graphinfo response must be a list")
    return [WebGraphRelease.model_validate(item) for item in payload]


def latest_web_graph_release(
    graphinfo_url: str = GRAPHINFO_URL,
    timeout_seconds: float = 30,
) -> WebGraphRelease:
    releases = fetch_web_graph_releases(graphinfo_url, timeout_seconds)
    if not releases:
        raise ValueError("Common Crawl graphinfo response did not contain releases")
    return releases[0]


def domain_graph_files(release_id: str) -> DomainGraphFiles:
    prefix = f"{DATA_BASE_URL}/{release_id}/domain/{release_id}-domain"
    return DomainGraphFiles(
        vertices_url=f"{prefix}-vertices.txt.gz",
        edges_url=f"{prefix}-edges.txt.gz",
        ranks_url=f"{prefix}-ranks.txt.gz",
        stats_url=f"{prefix}.stats",
    )


def fetch_domain_graph_stats(
    release_id: str,
    timeout_seconds: float = 30,
) -> dict[str, int | float | str]:
    text = _fetch_text(domain_graph_files(release_id).stats_url, timeout_seconds)
    return parse_stats_text(text)


def fetch_domain_vertex_sample(
    release_id: str,
    max_lines: int = 5,
    timeout_seconds: float = 30,
) -> list[DomainVertex]:
    files = domain_graph_files(release_id)
    lines = fetch_gzip_text_lines(
        files.vertices_url,
        max_lines=max_lines,
        timeout_seconds=timeout_seconds,
    )
    return [parse_domain_vertex_line(line) for line in lines]


def fetch_domain_vertices_for_domains(
    release_id: str,
    domains: set[str],
    max_lines: int | None = None,
    timeout_seconds: float = 30,
) -> dict[str, DomainVertex]:
    files = domain_graph_files(release_id)
    wanted = {to_reversed_domain_notation(normalize_domain(domain)) for domain in domains}
    found: dict[str, DomainVertex] = {}

    for line_number, line in enumerate(
        iter_gzip_text_lines(files.vertices_url, timeout_seconds),
        start=1,
    ):
        if max_lines is not None and line_number > max_lines:
            break

        vertex = parse_domain_vertex_line(line)
        if vertex.reversed_domain in wanted:
            found[vertex.domain] = vertex
            if len(found) == len(wanted):
                break

    return found


def fetch_domain_edges_for_targets(
    release_id: str,
    target_node_ids: set[int],
    max_lines: int | None = None,
    max_matches: int | None = None,
    timeout_seconds: float = 30,
) -> list[DomainEdge]:
    files = domain_graph_files(release_id)
    matches: list[DomainEdge] = []

    for line_number, line in enumerate(
        iter_gzip_text_lines(files.edges_url, timeout_seconds),
        start=1,
    ):
        if max_lines is not None and line_number > max_lines:
            break

        edge = parse_domain_edge_line(line)
        if edge.target_node_id not in target_node_ids:
            continue

        matches.append(edge)
        if max_matches is not None and len(matches) >= max_matches:
            break

    return matches


def fetch_vertices_by_node_id(
    release_id: str,
    node_ids: set[int],
    max_lines: int | None = None,
    timeout_seconds: float = 30,
) -> dict[int, DomainVertex]:
    files = domain_graph_files(release_id)
    found: dict[int, DomainVertex] = {}

    for line_number, line in enumerate(
        iter_gzip_text_lines(files.vertices_url, timeout_seconds),
        start=1,
    ):
        if max_lines is not None and line_number > max_lines:
            break

        vertex = parse_domain_vertex_line(line)
        if vertex.node_id in node_ids:
            found[vertex.node_id] = vertex
            if len(found) == len(node_ids):
                break

    return found


def iter_gzip_text_lines(url: str, timeout_seconds: float = 30) -> Iterator[str]:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with (
        urlopen(request, timeout=timeout_seconds) as response,
        gzip.GzipFile(fileobj=response) as gzip_file,
    ):
        while True:
            raw_line = gzip_file.readline()
            if not raw_line:
                break
            yield raw_line.decode("utf-8").rstrip("\n")


def fetch_gzip_text_lines(
    url: str,
    max_lines: int,
    timeout_seconds: float = 30,
) -> list[str]:
    if max_lines < 1:
        raise ValueError("max_lines must be positive")

    return list(islice(iter_gzip_text_lines(url, timeout_seconds), max_lines))


def parse_domain_vertex_line(line: str) -> DomainVertex:
    parts = line.split("\t")
    if len(parts) != 3:
        raise ValueError(f"expected vertex line with 3 tab-separated fields, got {line!r}")

    node_id = int(parts[0])
    reversed_domain = parts[1]
    num_hosts = int(parts[2])
    return DomainVertex(
        node_id=node_id,
        reversed_domain=reversed_domain,
        domain=reverse_domain_notation(reversed_domain),
        num_hosts=num_hosts,
    )


def parse_domain_edge_line(line: str) -> DomainEdge:
    parts = line.split("\t")
    if len(parts) != 2:
        raise ValueError(f"expected edge line with 2 tab-separated fields, got {line!r}")
    return DomainEdge(source_node_id=int(parts[0]), target_node_id=int(parts[1]))


def parse_domain_rank_line(line: str) -> DomainRank | None:
    if line.startswith("#"):
        return None

    parts = line.split("\t")
    if len(parts) != 6:
        raise ValueError(f"expected rank line with 6 tab-separated fields, got {line!r}")

    reversed_domain = parts[4]
    return DomainRank(
        harmonicc_position=int(parts[0]),
        harmonicc_value=float(parts[1]),
        pagerank_position=int(parts[2]),
        pagerank=float(parts[3]),
        reversed_domain=reversed_domain,
        domain=reverse_domain_notation(reversed_domain),
        num_hosts=int(parts[5]),
    )


def reverse_domain_notation(value: str) -> str:
    return ".".join(reversed(value.split(".")))


def to_reversed_domain_notation(value: str) -> str:
    return ".".join(reversed(value.split(".")))


def parse_stats_text(text: str) -> dict[str, int | float | str]:
    stats: dict[str, int | float | str] = {}
    for line in text.splitlines():
        if not line or "=" not in line:
            continue
        key, value = line.split("=", maxsplit=1)
        stats[key] = _parse_stat_value(value)
    return stats


def _fetch_json(url: str, timeout_seconds: float) -> Any:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=timeout_seconds) as response:
        return json.load(response)


def _fetch_text(url: str, timeout_seconds: float) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=timeout_seconds) as response:
        payload = response.read()
    if not isinstance(payload, bytes):
        raise TypeError("expected bytes response")
    return payload.decode("utf-8")


def _parse_stat_value(value: str) -> int | float | str:
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def release_ids_by_crawl(releases: list[WebGraphRelease]) -> Mapping[str, tuple[str, ...]]:
    return {release.id: release.crawls for release in releases}
