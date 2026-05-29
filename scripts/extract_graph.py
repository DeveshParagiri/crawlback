"""Run the bounded Common Crawl Web Graph extraction.

Streams the configured domain graph release, filters to Omni and competitor
targets, and writes resumable CSV checkpoints under data/extracts.
"""

import argparse
import logging
from pathlib import Path

from crawlback.config import load_competitor_config, load_extraction_config
from crawlback.graph_extract import extract_common_crawl_domain_graph


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract filtered Common Crawl graph data.")
    parser.add_argument("--companies", default="configs/competitors.yml")
    parser.add_argument("--extraction", default="configs/extraction.yml")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--timeout-seconds", type=float, default=120)
    parser.add_argument("--progress-every", type=int, default=10_000_000)
    parser.add_argument("--max-edge-lines", type=int, default=None)
    parser.add_argument("--max-edge-matches", type=int, default=None)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    companies = load_competitor_config(Path(args.companies))
    extraction = load_extraction_config(Path(args.extraction))
    output_dir = (
        Path(args.output_dir)
        if args.output_dir is not None
        else Path("data") / "extracts" / extraction.graph_release_id
    )

    result = extract_common_crawl_domain_graph(
        release_id=extraction.graph_release_id,
        companies=companies,
        output_dir=output_dir,
        max_edge_lines=args.max_edge_lines,
        max_edge_matches=args.max_edge_matches,
        timeout_seconds=args.timeout_seconds,
        progress_every=args.progress_every,
    )

    print(f"output_dir={result.paths.output_dir}")
    print(f"target_vertices={result.counts.target_vertices}")
    print(f"scanned_edges={result.counts.scanned_edges}")
    print(f"filtered_edges={result.counts.filtered_edges}")
    print(f"source_vertices={result.counts.source_vertices}")
    print(f"domain_ranks={result.counts.domain_ranks}")
    print(f"graph_edges={result.counts.graph_edges}")


if __name__ == "__main__":
    main()
