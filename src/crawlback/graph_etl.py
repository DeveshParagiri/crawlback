"""Graph edge transformation logic.

Converts graph edge inputs into raw backlink edge records. Filters for Omni and
configured competitors, maps target domains to companies, marks high-authority
sources, and deduplicates source-to-target observations before loading.
"""

from collections.abc import Iterable, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator

from crawlback.common_crawl import DomainEdge, DomainVertex
from crawlback.config import CompetitorConfig
from crawlback.models import RawDomainEdge
from crawlback.normalize_domains import normalize_domain

RANK_BUCKET_ORDER = {
    "top_10k": 0,
    "top_100k": 1,
    "top_1m": 2,
    "long_tail": 3,
}


class GraphEdgeInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_domain: str
    target_domain: str
    edge_weight: int | None = Field(default=None, ge=0)
    source_domain_rank_bucket: str | None = None

    @field_validator("source_domain", "target_domain", mode="before")
    @classmethod
    def normalize_domains(cls, value: object) -> str:
        return normalize_domain(str(value))


def graph_edge_inputs_from_common_crawl_edges(
    edges: Iterable[DomainEdge],
    source_vertices: Mapping[int, DomainVertex],
    target_vertices: Mapping[int, DomainVertex],
) -> list[GraphEdgeInput]:
    inputs: list[GraphEdgeInput] = []
    for edge in edges:
        source = source_vertices.get(edge.source_node_id)
        target = target_vertices.get(edge.target_node_id)
        if source is None or target is None:
            continue
        inputs.append(
            GraphEdgeInput(
                source_domain=source.domain,
                target_domain=target.domain,
                edge_weight=1,
            )
        )
    return inputs


def build_domain_edges(
    graph_release_id: str,
    rows: Iterable[GraphEdgeInput],
    companies: CompetitorConfig,
    high_authority_rank_buckets: set[str],
) -> list[RawDomainEdge]:
    grouped: dict[tuple[str, str, str], RawDomainEdge] = {}

    for row in rows:
        target_company = companies.company_for_domain(row.target_domain)
        if target_company is None:
            continue

        key = (row.source_domain, row.target_domain, target_company.company)
        edge = RawDomainEdge(
            graph_release_id=graph_release_id,
            source_domain=row.source_domain,
            target_domain=row.target_domain,
            target_company=target_company.company,
            target_segment=target_company.segment,
            edge_weight=row.edge_weight,
            source_domain_rank_bucket=row.source_domain_rank_bucket,
            source_high_authority_flag=row.source_domain_rank_bucket in high_authority_rank_buckets,
        )
        grouped[key] = _merge_edges(grouped.get(key), edge)

    return sorted(grouped.values(), key=lambda edge: (edge.source_domain, edge.target_company))


def _merge_edges(existing: RawDomainEdge | None, incoming: RawDomainEdge) -> RawDomainEdge:
    if existing is None:
        return incoming

    return existing.model_copy(
        update={
            "edge_weight": _merge_edge_weight(existing.edge_weight, incoming.edge_weight),
            "source_domain_rank_bucket": _best_rank_bucket(
                existing.source_domain_rank_bucket,
                incoming.source_domain_rank_bucket,
            ),
            "source_high_authority_flag": (
                existing.source_high_authority_flag or incoming.source_high_authority_flag
            ),
        }
    )


def _merge_edge_weight(left: int | None, right: int | None) -> int | None:
    if left is None:
        return right
    if right is None:
        return left
    return left + right


def _best_rank_bucket(left: str | None, right: str | None) -> str | None:
    if left is None:
        return right
    if right is None:
        return left
    left_order = RANK_BUCKET_ORDER.get(left, len(RANK_BUCKET_ORDER))
    right_order = RANK_BUCKET_ORDER.get(right, len(RANK_BUCKET_ORDER))
    return left if left_order <= right_order else right
