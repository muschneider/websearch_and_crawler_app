"""Unit tests for the PageExtractor's pure HTML-parsing layer.

No browser is launched - we feed static fixtures through
``PageExtractor.parse_html`` and assert on the structured output.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from websearch_api.extractors.page import PageExtractor

FIXTURES_DIR = Path(__file__).parent / "fixtures"
ARTICLE_BASE_URL = "https://blog.example.com/articles/why-async-python-matters"


@pytest.fixture
def article_html() -> str:
    return (FIXTURES_DIR / "article.html").read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# Canonical head/meta fields                                                  #
# --------------------------------------------------------------------------- #
def test_parse_html_extracts_canonical_head_fields(article_html: str) -> None:
    out = PageExtractor.parse_html(article_html, base_url=ARTICLE_BASE_URL)

    assert out["title"] == "Why Async Python Matters | Example Blog"
    assert out["description"] == (
        "A pragmatic look at when async/await actually helps and when it "
        "just adds complexity for no real gain."
    )
    assert out["author"] == "Jane Developer"
    assert out["language"] == "en"
    assert out["site_name"] == "Example Blog"
    assert out["published_at"] == "2026-04-12T09:00:00Z"


def test_parse_html_resolves_relative_canonical_and_favicon(article_html: str) -> None:
    md = PageExtractor.parse_html(article_html, base_url=ARTICLE_BASE_URL)["metadata"]

    assert md["canonical"] == "https://blog.example.com/articles/why-async-python-matters"
    assert md["favicon"] == "https://blog.example.com/favicon.ico"
    # og:* tags are preserved in the catch-all metadata bag.
    assert md["og:image"] == "https://blog.example.com/images/cover.png"
    assert md["twitter:card"] == "summary_large_image"


# --------------------------------------------------------------------------- #
# Main-content text + markdown                                                #
# --------------------------------------------------------------------------- #
def test_parse_html_strips_chrome_from_text(article_html: str) -> None:
    text = PageExtractor.parse_html(article_html, base_url=ARTICLE_BASE_URL)["text"]

    assert "Asynchronous programming in Python" in text
    # Nav / aside / footer must be removed by readability.
    assert "Home" not in text
    assert "Privacy" not in text
    assert "Back to top" not in text
    assert "Email the editor" not in text
    # Tracking-pixel script body must be gone.
    assert "tracking pixel" not in text


def test_parse_html_renders_markdown_with_atx_headings(article_html: str) -> None:
    md = PageExtractor.parse_html(article_html, base_url=ARTICLE_BASE_URL)["markdown"]

    assert md.startswith("# Why Async Python Matters")
    assert "## When async actually helps" in md
    assert "## Common pitfalls" in md
    # Inline links are converted to the markdown anchor form.
    assert "[asyncio](https://docs.python.org/3/library/asyncio.html)" in md
    assert "[FastAPI](https://fastapi.tiangolo.com/)" in md


# --------------------------------------------------------------------------- #
# Links                                                                       #
# --------------------------------------------------------------------------- #
def test_parse_html_extracts_only_main_content_links(article_html: str) -> None:
    links = PageExtractor.parse_html(article_html, base_url=ARTICLE_BASE_URL)["links"]
    urls = {str(link.url) for link in links}

    # In-content anchors (absolute + relative resolved against base_url).
    assert "https://docs.python.org/3/library/asyncio.html" in urls
    assert "https://fastapi.tiangolo.com/" in urls
    assert "https://github.com/agronholm/anyio" in urls
    assert "https://blog.example.com/articles/asyncio-cheatsheet" in urls

    # Boilerplate (nav/aside/footer) is filtered out by readability.
    assert not any("/about" in u for u in urls)
    assert not any("/privacy" in u for u in urls)
    assert not any("threading-vs-async" in u for u in urls)


def test_parse_html_skips_non_http_schemes(article_html: str) -> None:
    links = PageExtractor.parse_html(article_html, base_url=ARTICLE_BASE_URL)["links"]
    urls = {str(link.url) for link in links}

    assert not any(u.startswith("mailto:") for u in urls)
    assert not any(u.startswith("javascript:") for u in urls)
    assert not any(u.startswith("tel:") for u in urls)
    # And no fragment-only or stand-alone path anchors.
    assert "https://blog.example.com/#top" not in urls


def test_parse_html_preserves_rel_attribute(article_html: str) -> None:
    links = PageExtractor.parse_html(article_html, base_url=ARTICLE_BASE_URL)["links"]
    by_url = {str(link.url): link for link in links}

    fastapi_link = by_url["https://fastapi.tiangolo.com/"]
    assert fastapi_link.rel == "external nofollow"
    assert by_url["https://docs.python.org/3/library/asyncio.html"].rel is None


def test_parse_html_deduplicates_repeated_links() -> None:
    html = """
    <html><body><article>
      <p><a href="https://example.com/a">first</a></p>
      <p><a href="https://example.com/a">also first</a></p>
      <p><a href="https://example.com/b">second</a></p>
      <p>Filler sentence one. Filler sentence two with enough text for readability to keep the block.</p>
    </article></body></html>
    """
    links = PageExtractor.parse_html(html, base_url="https://example.com/")["links"]
    urls = [str(link.url) for link in links]
    assert urls == ["https://example.com/a", "https://example.com/b"]


# --------------------------------------------------------------------------- #
# Option flags                                                                #
# --------------------------------------------------------------------------- #
def test_parse_html_omits_html_when_not_requested(article_html: str) -> None:
    out = PageExtractor.parse_html(article_html, base_url=ARTICLE_BASE_URL, include_html=False)
    assert out["html"] is None


def test_parse_html_includes_html_when_requested(article_html: str) -> None:
    out = PageExtractor.parse_html(article_html, base_url=ARTICLE_BASE_URL, include_html=True)
    assert out["html"] is not None
    assert "<h1>Why Async Python Matters</h1>" in out["html"]
    # Boilerplate is stripped from the cleaned HTML too.
    assert "site-header" not in out["html"]


def test_parse_html_empty_links_when_disabled(article_html: str) -> None:
    out = PageExtractor.parse_html(article_html, base_url=ARTICLE_BASE_URL, include_links=False)
    assert out["links"] == []


# --------------------------------------------------------------------------- #
# Robustness                                                                  #
# --------------------------------------------------------------------------- #
def test_parse_html_handles_minimal_document() -> None:
    out = PageExtractor.parse_html(
        "<html><head></head><body><p>hello world</p></body></html>",
        base_url="https://x.test/",
    )
    assert out["title"] is None
    assert out["description"] is None
    assert "hello world" in out["text"]
    assert out["links"] == []


def test_parse_html_falls_back_to_og_title_when_no_title_tag() -> None:
    html = """
    <html><head>
      <meta property="og:title" content="OG-Only Title" />
    </head><body><article><p>body paragraph with enough content to survive trimming.</p></article></body></html>
    """
    out = PageExtractor.parse_html(html, base_url="https://x.test/")
    assert out["title"] == "OG-Only Title"


def test_parse_html_falls_back_to_og_locale_when_no_lang_attr() -> None:
    html = """
    <html><head>
      <title>Doc</title>
      <meta property="og:locale" content="pt_BR" />
    </head><body><article><p>conteudo suficiente para passar.</p></article></body></html>
    """
    out = PageExtractor.parse_html(html, base_url="https://x.test/")
    assert out["language"] == "pt_BR"
