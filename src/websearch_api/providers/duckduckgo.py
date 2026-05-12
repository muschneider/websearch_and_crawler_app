"""DuckDuckGo search provider.

We target the lightweight HTML endpoint at ``html.duckduckgo.com/html`` because:

* It server-renders results - no JS execution required, so the parse is robust.
* It does not deploy a captcha for normal traffic.
* The DOM layout has been stable for years: ``div.result`` blocks containing
  an ``a.result__a`` anchor and an ``a.result__snippet`` body.

If DuckDuckGo eventually changes the layout we only need to tweak
:meth:`DuckDuckGoProvider.parse_html`.
"""

from __future__ import annotations

import logging
from typing import ClassVar
from urllib.parse import parse_qs, unquote, urlparse

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


class DuckDuckGoProvider(SearchProvider):
    """Search backed by ``https://html.duckduckgo.com/html/``."""

    name: ClassVar[str] = "duckduckgo"
    SEARCH_URL: ClassVar[str] = "https://html.duckduckgo.com/html/"

    async def search(self, query: str, *, max_results: int) -> list[SearchResult]:
        limit = self._clamp(max_results)
        logger.info("ddg.search", extra={"query": query, "limit": limit})

        async with self._browser.new_context() as ctx:
            page = await ctx.new_page()
            try:
                await page.goto(
                    f"{self.SEARCH_URL}?q={query}",
                    wait_until="domcontentloaded",
                )
                # The "no results" page also renders fast, so we cap the wait
                # rather than wait_for_selector which would error on empty SERPs.
                await page.wait_for_load_state("networkidle", timeout=5_000)
            except PlaywrightTimeoutError as exc:
                raise ProviderTimeoutError(
                    f"duckduckgo did not load within {self._settings.request_timeout_ms}ms"
                ) from exc
            except PlaywrightError as exc:
                raise ProviderUnavailableError(f"duckduckgo navigation failed: {exc}") from exc

            html = await page.content()

        if "Unfortunately, bots use DuckDuckGo too" in html or "anomaly-modal" in html:
            raise ProviderBlockedError("duckduckgo presented an anti-bot challenge")

        return self.parse_html(html, max_results=limit, source=self.name)

    # ------------------------------------------------------------------ #
    # Pure parser - unit-testable without a browser                      #
    # ------------------------------------------------------------------ #
    @staticmethod
    def parse_html(
        html: str, *, max_results: int, source: str = "duckduckgo"
    ) -> list[SearchResult]:
        """Parse DuckDuckGo HTML SERP into structured ``SearchResult`` rows.

        Returns an empty list when the SERP renders no results - callers should
        treat that as a successful-but-empty response.
        """
        soup = BeautifulSoup(html, "lxml")
        results: list[SearchResult] = []

        for rank, block in enumerate(soup.select("div.result"), start=1):
            if "result--ad" in (block.get("class") or []):
                # Skip sponsored results so callers get the organic top N.
                continue

            anchor = block.select_one("a.result__a")
            if anchor is None:
                continue

            title = anchor.get_text(strip=True)
            href = anchor.get("href") or ""
            url = _clean_ddg_url(href)
            if not url:
                continue

            snippet_el = block.select_one("a.result__snippet, .result__snippet")
            snippet = snippet_el.get_text(" ", strip=True) if snippet_el else None

            metadata: dict[str, str] = {}
            displayed_url_el = block.select_one(".result__url")
            if displayed_url_el:
                displayed = displayed_url_el.get_text(" ", strip=True)
                if displayed:
                    metadata["displayed_url"] = displayed

            try:
                results.append(
                    SearchResult(
                        title=title or url,
                        url=AnyHttpUrl(url),
                        snippet=snippet,
                        rank=len(results) + 1,
                        source=source,
                        metadata=metadata,
                    )
                )
            except ValidationError:
                logger.debug("skipping malformed ddg result at rank %d (url=%r)", rank, url)
                continue

            if len(results) >= max_results:
                break

        return results


def _clean_ddg_url(href: str) -> str | None:
    """DuckDuckGo wraps external links via ``//duckduckgo.com/l/?uddg=<encoded>``.

    Strip the redirect and decode the real target. Returns ``None`` for empty,
    relative-only, or otherwise unusable hrefs.
    """
    if not href:
        return None

    # Normalise schemeless ``//`` URLs.
    if href.startswith("//"):
        href = "https:" + href

    parsed = urlparse(href)
    if parsed.netloc.endswith("duckduckgo.com") and parsed.path in {"/l/", "/l"}:
        qs = parse_qs(parsed.query)
        target = qs.get("uddg", [""])[0]
        if target:
            return unquote(target)

    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return href

    return None
