"""Raw table creation and loading.

DuckDB and MotherDuck boundary code. Creates raw Common Crawl tables and inserts
already-validated ETL records, keeping source fetching and business mapping
separate from database writes.
"""

import re
from collections.abc import Sequence
from pathlib import Path

import duckdb

from crawlback.models import RawDomainEdge, RawDomainRank, RawWatLinkEvidence

DEFAULT_SCHEMA = "raw"
VALID_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def connect(database: str | Path = ":memory:") -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(database))


def create_raw_tables(conn: duckdb.DuckDBPyConnection, schema: str = DEFAULT_SCHEMA) -> None:
    schema_name = _quote_identifier(schema)
    conn.execute(f"create schema if not exists {schema_name}")
    conn.execute(
        f"""
        create table if not exists {schema_name}.raw_common_crawl_domain_edges (
            graph_release_id varchar not null,
            source_domain varchar not null,
            target_domain varchar not null,
            target_company varchar not null,
            target_segment varchar not null,
            edge_weight integer,
            source_domain_rank_bucket varchar,
            source_high_authority_flag boolean not null,
            loaded_at timestamp with time zone not null
        )
        """
    )
    conn.execute(
        f"""
        create table if not exists {schema_name}.raw_common_crawl_domain_ranks (
            graph_release_id varchar not null,
            rank_entity_type varchar not null,
            domain_or_host varchar not null,
            rank_position integer,
            harmonic_centrality double,
            pagerank double,
            rank_bucket varchar,
            loaded_at timestamp with time zone not null
        )
        """
    )
    conn.execute(
        f"""
        create table if not exists {schema_name}.raw_common_crawl_wat_link_evidence (
            crawl_id varchar not null,
            wat_file_path varchar not null,
            warc_record_id varchar,
            source_url varchar not null,
            source_domain varchar not null,
            source_host varchar not null,
            target_url varchar not null,
            target_domain varchar not null,
            target_company varchar not null,
            anchor_text varchar,
            rel varchar,
            is_nofollow boolean not null,
            page_title varchar,
            page_language varchar,
            http_status integer,
            content_type varchar,
            extracted_at timestamp with time zone not null
        )
        """
    )


def insert_domain_edges(
    conn: duckdb.DuckDBPyConnection,
    edges: Sequence[RawDomainEdge],
    schema: str = DEFAULT_SCHEMA,
) -> int:
    if not edges:
        return 0

    schema_name = _quote_identifier(schema)
    conn.executemany(
        f"""
        insert into {schema_name}.raw_common_crawl_domain_edges (
            graph_release_id,
            source_domain,
            target_domain,
            target_company,
            target_segment,
            edge_weight,
            source_domain_rank_bucket,
            source_high_authority_flag,
            loaded_at
        )
        values (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                edge.graph_release_id,
                edge.source_domain,
                edge.target_domain,
                edge.target_company,
                edge.target_segment,
                edge.edge_weight,
                edge.source_domain_rank_bucket,
                edge.source_high_authority_flag,
                edge.loaded_at,
            )
            for edge in edges
        ],
    )
    return len(edges)


def insert_domain_ranks(
    conn: duckdb.DuckDBPyConnection,
    ranks: Sequence[RawDomainRank],
    schema: str = DEFAULT_SCHEMA,
) -> int:
    if not ranks:
        return 0

    schema_name = _quote_identifier(schema)
    conn.executemany(
        f"""
        insert into {schema_name}.raw_common_crawl_domain_ranks (
            graph_release_id,
            rank_entity_type,
            domain_or_host,
            rank_position,
            harmonic_centrality,
            pagerank,
            rank_bucket,
            loaded_at
        )
        values (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                rank.graph_release_id,
                rank.rank_entity_type,
                rank.domain_or_host,
                rank.rank_position,
                rank.harmonic_centrality,
                rank.pagerank,
                rank.rank_bucket,
                rank.loaded_at,
            )
            for rank in ranks
        ],
    )
    return len(ranks)


def insert_wat_link_evidence(
    conn: duckdb.DuckDBPyConnection,
    evidence_rows: Sequence[RawWatLinkEvidence],
    schema: str = DEFAULT_SCHEMA,
) -> int:
    if not evidence_rows:
        return 0

    schema_name = _quote_identifier(schema)
    conn.executemany(
        f"""
        insert into {schema_name}.raw_common_crawl_wat_link_evidence (
            crawl_id,
            wat_file_path,
            warc_record_id,
            source_url,
            source_domain,
            source_host,
            target_url,
            target_domain,
            target_company,
            anchor_text,
            rel,
            is_nofollow,
            page_title,
            page_language,
            http_status,
            content_type,
            extracted_at
        )
        values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                evidence.crawl_id,
                evidence.wat_file_path,
                evidence.warc_record_id,
                evidence.source_url,
                evidence.source_domain,
                evidence.source_host,
                evidence.target_url,
                evidence.target_domain,
                evidence.target_company,
                evidence.anchor_text,
                evidence.rel,
                evidence.is_nofollow,
                evidence.page_title,
                evidence.page_language,
                evidence.http_status,
                evidence.content_type,
                evidence.extracted_at,
            )
            for evidence in evidence_rows
        ],
    )
    return len(evidence_rows)


def _quote_identifier(identifier: str) -> str:
    if not VALID_IDENTIFIER.fullmatch(identifier):
        raise ValueError(f"invalid database identifier: {identifier!r}")
    return f'"{identifier}"'
