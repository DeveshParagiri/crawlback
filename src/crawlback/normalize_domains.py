"""URL, host, and registered-domain normalization.

Shared URL, host, and registered-domain cleanup for config parsing, record
validation, graph mapping, and WAT evidence. Keeps host and domain grains
separate so Common Crawl data is not mixed incorrectly.
"""

from urllib.parse import urlparse

import tldextract


def normalize_domain(value: str) -> str:
    stripped = value.strip().lower()
    if not stripped:
        raise ValueError("domain cannot be empty")

    parsed = urlparse(stripped if "://" in stripped else f"https://{stripped}")
    host = parsed.hostname
    if host is None:
        raise ValueError(f"could not parse domain from {value!r}")

    extracted = tldextract.extract(host)
    registered_domain = extracted.top_domain_under_public_suffix
    if not registered_domain:
        raise ValueError(f"could not resolve registered domain from {value!r}")
    return registered_domain


def normalize_host(value: str) -> str:
    stripped = value.strip().lower()
    if not stripped:
        raise ValueError("host cannot be empty")

    parsed = urlparse(stripped if "://" in stripped else f"https://{stripped}")
    if parsed.hostname is None:
        raise ValueError(f"could not parse host from {value!r}")
    return parsed.hostname


def validate_absolute_url(value: str) -> str:
    stripped = value.strip()
    parsed = urlparse(stripped)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"expected absolute URL, got {value!r}")
    return stripped
