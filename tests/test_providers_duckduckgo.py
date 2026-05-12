"""Unit tests for the DuckDuckGo provider's pure parser."""

from __future__ import annotations

from websearch_api.providers.duckduckgo import DuckDuckGoProvider, _clean_ddg_url


def test_parse_html_extracts_organic_results(ddg_results_html: str) -> None:
    results = DuckDuckGoProvider.parse_html(ddg_results_html, max_results=10)

    # Three organic results in the fixture; the ad and the malformed block are skipped.
    assert len(results) == 3
    titles = [r.title for r in results]
    assert titles == [
        "Python downloads page",
        "Python 3 docs",
        "Real Python",
    ]

    first = results[0]
    assert str(first.url) == "https://python.org/downloads"
    assert "Python Programming Language" in (first.snippet or "")
    assert first.rank == 1
    assert first.source == "duckduckgo"
    assert first.metadata.get("displayed_url") == "python.org/downloads"


def test_parse_html_honours_max_results(ddg_results_html: str) -> None:
    results = DuckDuckGoProvider.parse_html(ddg_results_html, max_results=2)
    assert len(results) == 2
    assert [r.rank for r in results] == [1, 2]


def test_parse_html_returns_empty_for_no_results(ddg_empty_html: str) -> None:
    assert DuckDuckGoProvider.parse_html(ddg_empty_html, max_results=10) == []


def test_clean_ddg_url_unwraps_redirect() -> None:
    href = "//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fa%2Fb&rut=abc"
    assert _clean_ddg_url(href) == "https://example.com/a/b"


def test_clean_ddg_url_passes_through_direct_links() -> None:
    assert _clean_ddg_url("https://example.com/x") == "https://example.com/x"


def test_clean_ddg_url_rejects_unusable_input() -> None:
    assert _clean_ddg_url("") is None
    assert _clean_ddg_url("javascript:void(0)") is None
    assert _clean_ddg_url("/internal/path") is None


def test_results_are_sequentially_ranked(ddg_results_html: str) -> None:
    results = DuckDuckGoProvider.parse_html(ddg_results_html, max_results=10)
    assert [r.rank for r in results] == list(range(1, len(results) + 1))
