"""Load graph extraction checkpoints into the raw database schema.

Reads graph_edges.csv and domain_ranks.csv, replaces rows for the configured
graph release, and leaves dbt to build the analytics schema.
"""

import argparse
import os
from pathlib import Path

import duckdb

from crawlback.config import CompetitorConfig, load_competitor_config, load_extraction_config
from crawlback.motherduck import connect, create_raw_tables


def main() -> None:
    parser = argparse.ArgumentParser(description="Load filtered graph CSVs into DuckDB.")
    parser.add_argument("--companies", default="configs/competitors.yml")
    parser.add_argument("--extraction", default="configs/extraction.yml")
    parser.add_argument("--database", default="data/crawlback.duckdb")
    parser.add_argument("--extract-dir", default=None)
    args = parser.parse_args()

    companies = load_competitor_config(Path(args.companies))
    extraction = load_extraction_config(Path(args.extraction))
    extract_dir = (
        Path(args.extract_dir)
        if args.extract_dir is not None
        else Path("data") / "extracts" / extraction.graph_release_id
    )

    graph_edges_path = extract_dir / "graph_edges.csv"
    domain_ranks_path = extract_dir / "domain_ranks.csv"

    database = _resolve_database(args.database)
    conn = connect(database)
    create_raw_tables(conn)
    _load_company_domains(conn, companies)

    conn.execute(
        "delete from raw.raw_common_crawl_domain_edges where graph_release_id = ?",
        [extraction.graph_release_id],
    )
    conn.execute(
        "delete from raw.raw_common_crawl_domain_ranks where graph_release_id = ?",
        [extraction.graph_release_id],
    )

    edge_count = _insert_graph_edges(conn, extraction.graph_release_id, graph_edges_path)
    rank_count = _insert_domain_ranks(conn, extraction.graph_release_id, domain_ranks_path)

    print(f"database={_display_database(database)}")
    print(f"raw_domain_edges_inserted={edge_count}")
    print(f"raw_domain_ranks_inserted={rank_count}")


def _resolve_database(database: str) -> str:
    if database not in {"motherduck", "md"}:
        return database

    token = os.environ.get("MOTHERDUCK_TOKEN")
    if not token:
        raise RuntimeError("MOTHERDUCK_TOKEN must be set when --database motherduck is used")
    database_name = os.environ.get("MOTHERDUCK_DATABASE", "crawlback")
    return f"md:{database_name}?motherduck_token={token}"


def _display_database(database: str) -> str:
    if "motherduck_token=" not in database:
        return database
    return database.split("?motherduck_token=", maxsplit=1)[0] + "?motherduck_token=<redacted>"


def _load_company_domains(conn: duckdb.DuckDBPyConnection, companies: CompetitorConfig) -> None:
    conn.execute(
        """
        create or replace temporary table company_domains (
            target_domain varchar,
            target_company varchar,
            target_segment varchar
        )
        """
    )
    conn.executemany(
        "insert into company_domains values (?, ?, ?)",
        [
            (domain, company.company, company.segment)
            for company in companies.companies
            for domain in company.domains
        ],
    )


def _insert_graph_edges(
    conn: duckdb.DuckDBPyConnection,
    graph_release_id: str,
    graph_edges_path: Path,
) -> int:
    conn.execute(
        """
        insert into raw.raw_common_crawl_domain_edges (
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
        with input_edges as (
            select
                lower(source_domain) as source_domain,
                lower(target_domain) as target_domain,
                coalesce(try_cast(edge_weight as integer), 1) as edge_weight,
                nullif(source_domain_rank_bucket, '') as source_domain_rank_bucket
            from read_csv_auto(?)
        ),
        mapped as (
            select
                input_edges.source_domain,
                input_edges.target_domain,
                company_domains.target_company,
                company_domains.target_segment,
                sum(input_edges.edge_weight) as edge_weight,
                case
                    when max(case
                        when input_edges.source_domain_rank_bucket = 'top_10k' then 1
                        else 0
                    end) = 1 then 'top_10k'
                    when max(case
                        when input_edges.source_domain_rank_bucket = 'top_100k' then 1
                        else 0
                    end) = 1 then 'top_100k'
                    when max(case
                        when input_edges.source_domain_rank_bucket = 'top_1m' then 1
                        else 0
                    end) = 1 then 'top_1m'
                    when max(case
                        when input_edges.source_domain_rank_bucket = 'long_tail' then 1
                        else 0
                    end) = 1 then 'long_tail'
                    else null
                end as source_domain_rank_bucket
            from input_edges
            join company_domains
              on input_edges.target_domain = company_domains.target_domain
            group by
                input_edges.source_domain,
                input_edges.target_domain,
                company_domains.target_company,
                company_domains.target_segment
        )
        select
            ? as graph_release_id,
            source_domain,
            target_domain,
            target_company,
            target_segment,
            edge_weight,
            source_domain_rank_bucket,
            source_domain_rank_bucket in ('top_10k', 'top_100k') as source_high_authority_flag,
            current_timestamp as loaded_at
        from mapped
        """,
        [str(graph_edges_path), graph_release_id],
    )
    return _count_rows(
        conn,
        """
        select count(*)
        from raw.raw_common_crawl_domain_edges
        where graph_release_id = ?
        """,
        graph_release_id,
    )


def _insert_domain_ranks(
    conn: duckdb.DuckDBPyConnection,
    graph_release_id: str,
    domain_ranks_path: Path,
) -> int:
    conn.execute(
        """
        insert into raw.raw_common_crawl_domain_ranks (
            graph_release_id,
            rank_entity_type,
            domain_or_host,
            rank_position,
            harmonic_centrality,
            pagerank,
            rank_bucket,
            loaded_at
        )
        select
            ? as graph_release_id,
            rank_entity_type,
            lower(domain_or_host) as domain_or_host,
            try_cast(rank_position as integer) as rank_position,
            try_cast(harmonic_centrality as double) as harmonic_centrality,
            try_cast(pagerank as double) as pagerank,
            nullif(rank_bucket, '') as rank_bucket,
            current_timestamp as loaded_at
        from read_csv_auto(?)
        """,
        [graph_release_id, str(domain_ranks_path)],
    )
    return _count_rows(
        conn,
        """
        select count(*)
        from raw.raw_common_crawl_domain_ranks
        where graph_release_id = ?
        """,
        graph_release_id,
    )


def _count_rows(conn: duckdb.DuckDBPyConnection, sql: str, graph_release_id: str) -> int:
    row = conn.execute(sql, [graph_release_id]).fetchone()
    if row is None:
        raise RuntimeError("count query did not return a row")
    return int(row[0])


if __name__ == "__main__":
    main()
