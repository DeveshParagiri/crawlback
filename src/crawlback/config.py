"""Project configuration models.

Owns versioned pipeline inputs: the Omni and competitor domain map, graph
release, crawl ID, and high-authority rank buckets. ETL code uses these models
to map domains to companies consistently before loading raw tables.
"""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from crawlback.normalize_domains import normalize_domain


class CompanyConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    company: str
    role: Literal["target", "competitor"]
    segment: str
    domains: tuple[str, ...] = Field(min_length=1)

    @field_validator("domains", mode="before")
    @classmethod
    def normalize_domains(cls, value: object) -> tuple[str, ...]:
        if not isinstance(value, list):
            raise TypeError("domains must be a list")
        normalized = tuple(normalize_domain(str(domain)) for domain in value)
        if len(set(normalized)) != len(normalized):
            raise ValueError("domains must be unique within a company")
        return normalized


class CompetitorConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    companies: tuple[CompanyConfig, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_target(self) -> "CompetitorConfig":
        targets = [company for company in self.companies if company.role == "target"]
        if len(targets) != 1:
            raise ValueError("competitor config must contain exactly one target company")

        all_domains = [domain for company in self.companies for domain in company.domains]
        if len(set(all_domains)) != len(all_domains):
            raise ValueError("domains must be unique across companies")

        return self

    @property
    def target_company(self) -> CompanyConfig:
        return next(company for company in self.companies if company.role == "target")

    @property
    def competitor_companies(self) -> tuple[CompanyConfig, ...]:
        return tuple(company for company in self.companies if company.role == "competitor")

    def company_for_domain(self, domain: str) -> CompanyConfig | None:
        normalized = normalize_domain(domain)
        for company in self.companies:
            if normalized in company.domains:
                return company
        return None


class ExtractionConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    graph_release_id: str = Field(min_length=1)
    crawl_id: str = Field(min_length=1)
    max_wat_enrichment_domains: int = Field(gt=0)
    high_authority_rank_buckets: tuple[str, ...] = Field(min_length=1)

    @field_validator("high_authority_rank_buckets", mode="before")
    @classmethod
    def validate_rank_buckets(cls, value: object) -> tuple[str, ...]:
        if not isinstance(value, list):
            raise TypeError("high_authority_rank_buckets must be a list")
        buckets = tuple(str(bucket) for bucket in value)
        if len(set(buckets)) != len(buckets):
            raise ValueError("high_authority_rank_buckets must be unique")
        return buckets


def _load_yaml(path: Path) -> object:
    with path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def load_competitor_config(path: Path) -> CompetitorConfig:
    return CompetitorConfig.model_validate(_load_yaml(path))


def load_extraction_config(path: Path) -> ExtractionConfig:
    return ExtractionConfig.model_validate(_load_yaml(path))
