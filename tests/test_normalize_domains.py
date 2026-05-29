import pytest

from crawlback.normalize_domains import normalize_domain, normalize_host, validate_absolute_url


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://www.omni.co/path?q=1", "omni.co"),
        ("SIGMACOMPUTING.COM", "sigmacomputing.com"),
        ("blog.hex.tech/posts", "hex.tech"),
    ],
)
def test_normalize_domain_returns_registered_domain(raw: str, expected: str) -> None:
    assert normalize_domain(raw) == expected


def test_normalize_domain_rejects_empty_string() -> None:
    with pytest.raises(ValueError, match="domain cannot be empty"):
        normalize_domain("")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://blog.hex.tech/posts", "blog.hex.tech"),
        ("WWW.OMNI.CO/path", "www.omni.co"),
    ],
)
def test_normalize_host_preserves_host(raw: str, expected: str) -> None:
    assert normalize_host(raw) == expected


def test_normalize_host_rejects_empty_string() -> None:
    with pytest.raises(ValueError, match="host cannot be empty"):
        normalize_host("")


def test_validate_absolute_url_strips_valid_url() -> None:
    assert validate_absolute_url(" https://www.omni.co/path ") == "https://www.omni.co/path"


def test_validate_absolute_url_rejects_relative_url() -> None:
    with pytest.raises(ValueError, match="expected absolute URL"):
        validate_absolute_url("/relative/path")
