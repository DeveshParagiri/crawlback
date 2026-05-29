from pathlib import Path

from crawlback.config import load_competitor_config, load_extraction_config


def test_load_competitor_config_excludes_power_bi() -> None:
    config = load_competitor_config(Path("configs/competitors.yml"))

    company_names = {company.company for company in config.companies}

    assert "Omni" in company_names
    assert "Tableau" in company_names
    assert "Power BI" not in company_names


def test_load_competitor_config_has_exactly_one_target() -> None:
    config = load_competitor_config(Path("configs/competitors.yml"))

    targets = [company for company in config.companies if company.role == "target"]

    assert len(targets) == 1
    assert targets[0].domains == ("omni.co",)


def test_competitor_config_maps_domains_to_companies() -> None:
    config = load_competitor_config(Path("configs/competitors.yml"))

    company = config.company_for_domain("https://www.tableau.com/products")

    assert company is not None
    assert company.company == "Tableau"
    assert company.segment == "enterprise_incumbent"


def test_load_extraction_config() -> None:
    config = load_extraction_config(Path("configs/extraction.yml"))

    assert config.max_wat_enrichment_domains == 500
    assert config.high_authority_rank_buckets == ("top_10k", "top_100k")
