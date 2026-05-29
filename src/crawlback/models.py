"""Validated raw record shapes.

Pydantic models for rows entering the raw layer: domain graph edges, graph rank
rows, and WAT link evidence. They normalize domains and enforce basic validity
before data reaches DuckDB, MotherDuck, dbt, or Omni.
"""

from datetime import UTC, datetime
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from crawlback.normalize_domains import normalize_domain, normalize_host, validate_absolute_url


def _clean_optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


class RawDomainEdge(BaseModel):
    model_config = ConfigDict(frozen=True)

    graph_release_id: str = Field(min_length=1)
    source_domain: str
    target_domain: str
    target_company: str = Field(min_length=1)
    target_segment: str = Field(min_length=1)
    edge_weight: int | None = Field(default=None, ge=0)
    source_domain_rank_bucket: str | None = None
    source_high_authority_flag: bool = False
    loaded_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("source_domain", "target_domain", mode="before")
    @classmethod
    def normalize_domains(cls, value: object) -> str:
        return normalize_domain(str(value))


class RawDomainRank(BaseModel):
    model_config = ConfigDict(frozen=True)

    graph_release_id: str = Field(min_length=1)
    rank_entity_type: Literal["domain", "host"]
    domain_or_host: str = Field(min_length=1)
    rank_position: int | None = Field(default=None, ge=1)
    harmonic_centrality: float | None = Field(default=None, ge=0)
    pagerank: float | None = Field(default=None, ge=0)
    rank_bucket: str | None = None
    loaded_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="before")
    @classmethod
    def normalize_rank_entity(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        domain_or_host = data.get("domain_or_host")
        rank_entity_type = data.get("rank_entity_type")
        if domain_or_host is None:
            return data
        if rank_entity_type == "host":
            normalized = normalize_host(str(domain_or_host))
        else:
            normalized = normalize_domain(str(domain_or_host))
        return {**data, "domain_or_host": normalized}


class RawWatLinkEvidence(BaseModel):
    model_config = ConfigDict(frozen=True)

    crawl_id: str = Field(min_length=1)
    wat_file_path: str = Field(min_length=1)
    warc_record_id: str | None = None
    source_url: str
    source_domain: str
    source_host: str = Field(min_length=1)
    target_url: str
    target_domain: str
    target_company: str = Field(min_length=1)
    anchor_text: str | None = None
    rel: str | None = None
    is_nofollow: bool = False
    page_title: str | None = None
    page_language: str | None = None
    http_status: int | None = Field(default=None, ge=100, le=599)
    content_type: str | None = None
    extracted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="before")
    @classmethod
    def infer_nofollow(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        rel = data.get("rel")
        if rel is None:
            return data
        rel_parts = {part.strip().lower() for part in str(rel).split()}
        if "nofollow" not in rel_parts:
            return data
        return {**data, "is_nofollow": True}

    @field_validator("source_url", "target_url", mode="before")
    @classmethod
    def validate_urls(cls, value: object) -> str:
        return validate_absolute_url(str(value))

    @field_validator("source_domain", "target_domain", mode="before")
    @classmethod
    def normalize_domains(cls, value: object) -> str:
        return normalize_domain(str(value))

    @field_validator("source_host", mode="before")
    @classmethod
    def normalize_source_host(cls, value: object) -> str:
        return normalize_host(str(value))

    @field_validator(
        "warc_record_id",
        "anchor_text",
        "rel",
        "page_title",
        "page_language",
        "content_type",
        mode="before",
    )
    @classmethod
    def clean_optional_text(cls, value: object) -> str | None:
        return _clean_optional_text(value)

    @model_validator(mode="after")
    def validate_url_derived_fields(self) -> "RawWatLinkEvidence":
        source_host = urlparse(self.source_url).hostname
        if source_host is None:
            raise ValueError("source_url must contain a host")
        if self.source_host != source_host.lower():
            raise ValueError("source_host must match source_url host")
        if self.source_domain != normalize_domain(self.source_url):
            raise ValueError("source_domain must match source_url registered domain")
        if self.target_domain != normalize_domain(self.target_url):
            raise ValueError("target_domain must match target_url registered domain")

        return self
