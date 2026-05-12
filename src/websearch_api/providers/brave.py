"""Brave Search provider.

Brave Search (``search.brave.com``) ships a server-rendered HTML SERP that is
friendly to ``Playwright``-driven scraping: the result cards are present in
the initial HTML, no captcha gate, no SPA hydration required.

Layout (as of 2025-2026)::

    <div class="snippet" data-type="web">
      <div class="result-wrapper">
        <div class="result-content">
          <a href="https://target/url">
            <cite class="snippet-url">target.url</cite>
            <div class="title search-snippet-title">Page Title</div>
          </a>
          <div class="generic-snippet">
            <div class="content">snippet body...</div>
          </div>
        </div>
      </div>
    </div>

If Brave ever changes its DOM only :meth:`parse_html` needs to be updated.
"""

from __future__ import annotations

import contextlib
import logging
from typing import ClassVar
from urllib.parse import quote_plus

from bs4 import BeautifulSoup
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from pydantic import AnyHttpUrl, ValidationError

from websearch_api.exceptions import (
    ProviderBlockedError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from websearch_api.models import SearchResult
from websearch_api.providers.base import SearchProvider

logger = logging.getLogger(__name__)


class BraveSearchProvider(SearchProvider):
    """Search backed by ``https://search.brave.com/search``."""

    name: ClassVar[str] = "brave"
    SEARCH_URL: ClassVar[str] = "https://search.brave.com/search"

    async def search(self, query: str, *, max_results: int) -> list[SearchResult]:
        limit = self._clamp(max_results)
        logger.info("brave.search", extra={"query": query, "limit": limit})

        url = f"{self.SEARCH_URL}?q={quote_plus(query)}"
        async with self._browser.new_context() as ctx:
            page = await ctx.new_page()
            try:
                response = await page.goto(url, wait_until="domcontentloaded")
            except PlaywrightTimeoutError as exc:
                raise ProviderTimeoutError(
                    f"brave did not load within {self._settings.request_timeout_ms}ms"
                ) from exc
            except PlaywrightError as exc:
                raise ProviderUnavailableError(f"brave navigation failed: {exc}") from exc

            if response is None:
                raise ProviderUnavailableError("brave returned no response")
            if response.status == 429:
                raise ProviderBlockedError("brave rate-limited the request (429)")
            if response.status >= 400:
                raise ProviderUnavailableError(f"brave returned HTTP {response.status}")

            # Give the Svelte app a brief moment to finish hydration; the SERP
            # cards are already in the initial HTML, but a small settle helps
            # when Brave inlines lazy snippets. No results = legitimate empty response.
            with contextlib.suppress(PlaywrightTimeoutError):
                await page.wait_for_selector('div.snippet[data-type="web"]', timeout=5_000)

            html = await page.content()

        if _looks_like_block(html):
            raise ProviderBlockedError("brave returned an anti-bot challenge")

        return self.parse_html(html, max_results=limit, source=self.name)

    # ------------------------------------------------------------------ #
    # Pure parser - unit-testable without a browser                      #
    # ------------------------------------------------------------------ #
    @staticmethod
    def parse_html(html: str, *, max_results: int, source: str = "brave") -> list[SearchResult]:
        """Parse a Brave SERP into structured ``SearchResult`` rows."""
        soup = BeautifulSoup(html, "lxml")
        results: list[SearchResult] = []

        for block in soup.select('div.snippet[data-type="web"]'):
            link = block.select_one("a[href^=http]")
            if link is None:
                continue
            href = link.get("href") or ""

            title_el = block.select_one(
                "div.title.search-snippet-title, div.title, .search-snippet-title"
            )
            if title_el is None:
                # Fall back to the anchor's site-name label if no dedicated title.
                title_el = block.select_one(".site-name-content .text-ellipsis")
            title = title_el.get_text(" ", strip=True) if title_el else ""

            snippet_el = block.select_one("div.generic-snippet .content, div.snippet-content")
            snippet = snippet_el.get_text(" ", strip=True) if snippet_el else None

            cite_el = block.select_one("cite.snippet-url, cite")
            metadata: dict[str, str] = {}
            if cite_el:
                metadata["displayed_url"] = cite_el.get_text(" ", strip=True)

            try:
                results.append(
                    SearchResult(
                        title=title or href,
                        url=AnyHttpUrl(href),
                        snippet=snippet,
                        rank=len(results) + 1,
                        source=source,
                        metadata=metadata,
                    )
                )
            except ValidationError:
                logger.debug("skipping malformed brave result href=%r", href)
                continue

            if len(results) >= max_results:
                break

        return results


def _looks_like_block(html: str) -> bool:
    """Heuristic: detect Brave's bot/captcha gate."""
    needles = (
        "Are you human?",
        "captcha-bypass",
        "challenge-platform",
    )
    return any(needle in html for needle in needles)
