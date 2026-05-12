"""Single-URL page extractor.

Drives Playwright against an arbitrary URL, then runs the page HTML through a
``readability``-based content-extraction pipeline and produces:

* the main-content **text** (boilerplate-free),
* the same content as **Markdown**,
* the title / description / language / og-tags / canonical / favicon,
* the outbound **links** found inside the main content.

The HTML-parsing half lives in :meth:`PageExtractor.parse_html` as a pure
static method so it's unit-testable with fixtures alone, no browser required.
"""

from __future__ import annotations

import contextlib
import logging
import re
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from bs4.element import Tag
from markdownify import markdownify as _html_to_markdown
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from pydantic import AnyHttpUrl, ValidationError
from readability import Document

from websearch_api.browser.manager import BrowserManager
from websearch_api.config import Settings
from websearch_api.exceptions import (
    ProviderBlockedError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from websearch_api.models import PageLink

logger = logging.getLogger(__name__)

# Whitespace runs (incl. newlines, tabs) collapse to a single space when we
# build the plain-text field. Markdown output keeps its own newlines intact.
_WHITESPACE_RE = re.compile(r"\s+")


class PageExtractor:
    """Fetch + extract structured content from a single URL."""

    def __init__(self, browser: BrowserManager, settings: Settings) -> None:
        self._browser = browser
        self._settings = settings

    # ------------------------------------------------------------------ #
    # Live extraction                                                    #
    # ------------------------------------------------------------------ #
    async def extract(
        self,
        url: str,
        *,
        wait_for_selector: str | None = None,
        include_html: bool = False,
        include_links: bool = True,
    ) -> dict[str, Any]:
        """Fetch ``url`` with Playwright and return a parsed-page dict.

        The returned dict matches the shape of :class:`ExtractResponse` minus
        the ``url`` / ``elapsed_ms`` / ``fetched_at`` envelope fields, which
        the route handler fills in.
        """
        logger.info("extract.start", extra={"url": url})

        async with self._browser.new_context() as ctx:
            page = await ctx.new_page()
            try:
                response = await page.goto(url, wait_until="domcontentloaded")
            except PlaywrightTimeoutError as exc:
                raise ProviderTimeoutError(
                    f"{url} did not load within {self._settings.request_timeout_ms}ms"
                ) from exc
            except PlaywrightError as exc:
                raise ProviderUnavailableError(f"navigation to {url} failed: {exc}") from exc

            if response is None:
                raise ProviderUnavailableError(f"no response received from {url}")

            status = response.status
            final_url = page.url

            # 4xx/5xx are still "successful extractions" - we want to surface the
            # status_code to the caller. Only catastrophic failures bubble up as
            # exceptions. We do treat 429 specifically as a block signal.
            if status == 429:
                raise ProviderBlockedError(f"{url} rate-limited the request (429)")

            if wait_for_selector:
                with contextlib.suppress(PlaywrightTimeoutError):
                    await page.wait_for_selector(wait_for_selector, timeout=10_000)

            html = await page.content()

        parsed = self.parse_html(
            html,
            base_url=final_url,
            include_html=include_html,
            include_links=include_links,
        )
        parsed["status_code"] = status
        parsed["final_url"] = final_url
        return parsed

    # ------------------------------------------------------------------ #
    # Pure parser - unit-testable without a browser                      #
    # ------------------------------------------------------------------ #
    @staticmethod
    def parse_html(
        html: str,
        *,
        base_url: str,
        include_html: bool = False,
        include_links: bool = True,
    ) -> dict[str, Any]:
        """Turn raw HTML into a structured-content dict.

        ``base_url`` is used to resolve relative ``href`` values into absolute
        URLs (required for :class:`PageLink` validation).
        """
        # 1. Readability extracts the main article block + a heuristic title.
        try:
            doc = Document(html)
            main_html = doc.summary(html_partial=True)
            readability_title = doc.short_title() or None
        except Exception:  # pragma: no cover - readability is paranoid, never crash on it
            logger.debug("readability failed; falling back to <body>", exc_info=True)
            main_html = ""
            readability_title = None

        # 2. Soup the cleaned main-content HTML for text + links.
        main_soup = BeautifulSoup(main_html or "<div></div>", "lxml")
        text = _WHITESPACE_RE.sub(" ", main_soup.get_text(" ", strip=True)).strip()

        markdown = ""
        if main_html:
            markdown = _html_to_markdown(
                main_html,
                heading_style="ATX",
                strip=["script", "style"],
            ).strip()

        # 3. Soup the *whole* document for page-level metadata (head tags etc.).
        full_soup = BeautifulSoup(html, "lxml")
        metadata, head_fields = _extract_metadata(full_soup, base_url=base_url)

        # 4. Links from main content only - boilerplate nav links don't count.
        links: list[PageLink] = []
        if include_links:
            links = _extract_links(main_soup, base_url=base_url)

        title = head_fields.get("title") or readability_title

        return {
            "title": title,
            "description": head_fields.get("description"),
            "author": head_fields.get("author"),
            "language": head_fields.get("language"),
            "site_name": head_fields.get("site_name"),
            "published_at": head_fields.get("published_at"),
            "text": text,
            "markdown": markdown,
            "html": main_html if include_html else None,
            "links": links,
            "metadata": metadata,
        }


# --------------------------------------------------------------------------- #
# Internal helpers                                                            #
# --------------------------------------------------------------------------- #
def _extract_metadata(
    soup: BeautifulSoup, *, base_url: str
) -> tuple[dict[str, str], dict[str, str]]:
    """Return ``(metadata, head_fields)``.

    ``head_fields`` carries the canonical, typed values we lift onto the
    response (title, description, language, ...). ``metadata`` is the catch-all
    bag of remaining og:/twitter:/link tags useful to downstream consumers.
    """
    metadata: dict[str, str] = {}
    head: dict[str, str] = {}

    title_el = soup.find("title")
    if isinstance(title_el, Tag) and title_el.string:
        head["title"] = title_el.string.strip()

    html_el = soup.find("html")
    if isinstance(html_el, Tag):
        lang = html_el.get("lang")
        if isinstance(lang, str) and lang.strip():
            head["language"] = lang.strip()

    for meta in soup.find_all("meta"):
        if not isinstance(meta, Tag):
            continue
        name = (meta.get("name") or meta.get("property") or "").strip().lower()
        content = meta.get("content")
        if not name or not isinstance(content, str):
            continue
        content = content.strip()
        if not content:
            continue

        if name in ("description", "og:description") and "description" not in head:
            head["description"] = content
        elif name == "og:title" and "title" not in head:
            head["title"] = content
        elif name == "og:site_name":
            head["site_name"] = content
        elif name == "og:locale" and "language" not in head:
            head["language"] = content
        elif name == "author":
            head["author"] = content
        elif name in ("article:published_time", "datepublished", "date"):
            head.setdefault("published_at", content)
        else:
            metadata[name] = content

    # Canonical link + favicon land in the generic metadata bag.
    for link in soup.find_all("link"):
        if not isinstance(link, Tag):
            continue
        rel = link.get("rel")
        if isinstance(rel, list):
            rel_value = " ".join(rel).lower()
        elif isinstance(rel, str):
            rel_value = rel.lower()
        else:
            continue
        href = link.get("href")
        if not isinstance(href, str) or not href.strip():
            continue
        absolute = urljoin(base_url, href.strip())
        if "canonical" in rel_value:
            metadata.setdefault("canonical", absolute)
        elif "icon" in rel_value:
            metadata.setdefault("favicon", absolute)

    return metadata, head


def _extract_links(soup: BeautifulSoup, *, base_url: str) -> list[PageLink]:
    """Return all valid outbound links found inside ``soup``.

    Anchors with javascript:/mailto:/tel: schemes, fragment-only hrefs, or
    URLs that don't validate as ``AnyHttpUrl`` are silently skipped.
    """
    seen: set[str] = set()
    out: list[PageLink] = []

    for anchor in soup.find_all("a"):
        if not isinstance(anchor, Tag):
            continue
        href = anchor.get("href")
        if not isinstance(href, str):
            continue
        href = href.strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue

        absolute = urljoin(base_url, href)
        scheme = urlparse(absolute).scheme.lower()
        if scheme not in ("http", "https"):
            continue
        if absolute in seen:
            continue
        seen.add(absolute)

        text = anchor.get_text(" ", strip=True)
        rel_attr = anchor.get("rel")
        if isinstance(rel_attr, list):
            rel_value: str | None = " ".join(rel_attr) or None
        elif isinstance(rel_attr, str):
            rel_value = rel_attr or None
        else:
            rel_value = None

        try:
            out.append(PageLink(text=text or absolute, url=AnyHttpUrl(absolute), rel=rel_value))
        except ValidationError:
            continue

    return out
