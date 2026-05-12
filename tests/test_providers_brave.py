"""Unit tests for the Brave Search provider's pure parser."""

from __future__ import annotations

from pathlib import Path

import pytest

from websearch_api.providers.brave import BraveSearchProvider, _looks_like_block

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def brave_results_html() -> str:
    return (FIXTURES_DIR / "brave_results.html").read_text(encoding="utf-8")


def test_parse_html_extracts_web_results(brave_results_html: str) -> None:
    results = BraveSearchProvider.parse_html(brave_results_html, max_results=10)

    # 3 organic web results in the fixture. The news card and the malformed
    # web card without an anchor are both skipped.
    assert len(results) == 3
    titles = [r.title for r in results]
    assert titles == [
        "FastAPI",
        "Using FastAPI to Build Python Web APIs - Real Python",
        "tiangolo/fastapi - GitHub",
    ]

    first = results[0]
    assert str(first.url) == "https://fastapi.tiangolo.com/"
    assert first.snippet is not None
    assert "FastAPI is a modern, fast" in first.snippet
    assert first.rank == 1
    assert first.source == "brave"
    assert first.metadata.get("displayed_url") == "fastapi.tiangolo.com"


def test_parse_html_honours_max_results(brave_results_html: str) -> None:
    results = BraveSearchProvider.parse_html(brave_results_html, max_results=2)
    assert len(results) == 2
    assert [r.rank for r in results] == [1, 2]


def test_parse_html_returns_empty_for_no_results() -> None:
    assert BraveSearchProvider.parse_html("<html></html>", max_results=10) == []


def test_looks_like_block_detects_captcha() -> None:
    assert _looks_like_block("<html>Are you human? please verify...</html>") is True
    assert _looks_like_block("<html>normal content</html>") is False


def test_results_are_sequentially_ranked(brave_results_html: str) -> None:
    results = BraveSearchProvider.parse_html(brave_results_html, max_results=10)
    assert [r.rank for r in results] == list(range(1, len(results) + 1))
