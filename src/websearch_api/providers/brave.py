"""Brave Search provider.

Brave Search (``search.brave.com``) ships a server-rendered HTML SERP that is
friendly to scraping *once you're past the bot gate*. The gate is the hard
part: Brave fronts the site with Cloudflare-grade heuristics that look at the
IP, the TLS/HTTP-2 fingerprint, the request cadence, and the navigation
pattern. Fingerprint rotation alone is not enough — we also need to **behave**
like a returning human.

Strategy
--------
1.  **Persona rotation.** A coherent bundle of UA, viewport, locale, timezone,
    and HTTP client-hints. Each attempt picks one.
2.  **Stealth init script.** Neutralises the cheapest detectors (webdriver
    flag, empty plugins, missing ``window.chrome``, permissions mismatch,
    WebGL vendor leak).
3.  **Homepage → type → submit flow.** Instead of jumping straight to
    ``/search?q=...`` (a smoking gun — real users virtually never do this on
    a cold session), we load the homepage, click the search box, *type* the
    query with random per-keystroke delays, and press Enter. Cookies set on
    the homepage (including Cloudflare's ``cf_clearance``) carry into the
    search request automatically.
4.  **Per-persona cookie cache.** After a successful flow we capture
    ``storage_state`` and replay it on subsequent requests for the same
    persona — a returning user with valid clearance cookies is barely
    scrutinised. On 429 we evict the persona's cache (the cookies are
    poisoned) and let the retry pick a fresh identity.
5.  **Generous backoff.** Brave's 429 typically takes 10-60 seconds to clear
    at the edge. We back off accordingly with jitter.
6.  **Optional outbound proxy.** When your origin IP is on a public-cloud
    netblock, behaviour fixes are insufficient. Set ``WEBSEARCH_BRAVE_PROXY``
    to route the provider through a residential / datacenter pool.

If you control your traffic and need bulletproof results, the official
`Brave Search API <https://api.search.brave.com/>`_ is the right answer: a
free key gets you 2,000 queries/month without any of this dance.

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

import asyncio
import contextlib
import logging
import random
from dataclasses import dataclass
from typing import ClassVar
from urllib.parse import quote_plus

from bs4 import BeautifulSoup
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from pydantic import AnyHttpUrl, ValidationError

from websearch_api.browser.manager import BrowserManager
from websearch_api.config import Settings
from websearch_api.exceptions import (
    ProviderBlockedError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from websearch_api.models import SearchResult
from websearch_api.providers.base import SearchProvider

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Persona pool                                                                #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class _Persona:
    """A coherent identity bundle used for a single search attempt.

    All fields are correlated: a Windows-Chrome ``user_agent`` ships with the
    matching ``Sec-CH-UA-Platform`` and ``Accept-Language`` headers, etc. Mixing
    a macOS UA with a Windows platform header is exactly the kind of
    inconsistency anti-bot heuristics look for.
    """

    user_agent: str
    viewport: tuple[int, int]
    locale: str
    timezone_id: str
    accept_language: str
    sec_ch_ua: str | None  # None for non-Chromium UAs (Firefox)
    sec_ch_ua_platform: str | None
    sec_ch_ua_mobile: str = '"?0"'

    @property
    def extra_http_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/avif,image/webp,*/*;q=0.8"
            ),
            "Accept-Language": self.accept_language,
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Upgrade-Insecure-Requests": "1",
            "DNT": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
        }
        if self.sec_ch_ua:
            headers["Sec-CH-UA"] = self.sec_ch_ua
            headers["Sec-CH-UA-Mobile"] = self.sec_ch_ua_mobile
            if self.sec_ch_ua_platform:
                headers["Sec-CH-UA-Platform"] = self.sec_ch_ua_platform
        return headers


# Curated late-2025 / early-2026 desktop browser fingerprints. Each tuple is
# internally consistent (UA matches CH-UA, platform, common viewport).
_PERSONAS: tuple[_Persona, ...] = (
    # --- Chrome 132 on Windows 11 ---
    _Persona(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36"
        ),
        viewport=(1920, 1080),
        locale="en-US",
        timezone_id="America/New_York",
        accept_language="en-US,en;q=0.9",
        sec_ch_ua='"Google Chrome";v="132", "Chromium";v="132", "Not_A Brand";v="24"',
        sec_ch_ua_platform='"Windows"',
    ),
    _Persona(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
        viewport=(1536, 864),
        locale="en-GB",
        timezone_id="Europe/London",
        accept_language="en-GB,en;q=0.9",
        sec_ch_ua='"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        sec_ch_ua_platform='"Windows"',
    ),
    # --- Chrome 131/132 on macOS ---
    _Persona(
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36"
        ),
        viewport=(1440, 900),
        locale="en-US",
        timezone_id="America/Los_Angeles",
        accept_language="en-US,en;q=0.9",
        sec_ch_ua='"Google Chrome";v="132", "Chromium";v="132", "Not_A Brand";v="24"',
        sec_ch_ua_platform='"macOS"',
    ),
    _Persona(
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
        viewport=(1680, 1050),
        locale="en-US",
        timezone_id="America/Chicago",
        accept_language="en-US,en;q=0.8",
        sec_ch_ua='"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        sec_ch_ua_platform='"macOS"',
    ),
    # --- Edge 131 on Windows 11 ---
    _Persona(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0"
        ),
        viewport=(1920, 1080),
        locale="en-US",
        timezone_id="America/Denver",
        accept_language="en-US,en;q=0.9",
        sec_ch_ua='"Microsoft Edge";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        sec_ch_ua_platform='"Windows"',
    ),
    # --- Chrome 132 on Linux ---
    _Persona(
        user_agent=(
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36"
        ),
        viewport=(1920, 1080),
        locale="en-US",
        timezone_id="Europe/Berlin",
        accept_language="en-US,en;q=0.9,de;q=0.8",
        sec_ch_ua='"Google Chrome";v="132", "Chromium";v="132", "Not_A Brand";v="24"',
        sec_ch_ua_platform='"Linux"',
    ),
    # --- Firefox 133 on Windows ---
    _Persona(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0"
        ),
        viewport=(1366, 768),
        locale="en-US",
        timezone_id="America/New_York",
        accept_language="en-US,en;q=0.5",
        sec_ch_ua=None,  # Firefox doesn't send client hints
        sec_ch_ua_platform=None,
    ),
    # --- Firefox 133 on macOS ---
    _Persona(
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.6; rv:133.0) Gecko/20100101 Firefox/133.0"
        ),
        viewport=(1440, 900),
        locale="en-US",
        timezone_id="America/Los_Angeles",
        accept_language="en-US,en;q=0.5",
        sec_ch_ua=None,
        sec_ch_ua_platform=None,
    ),
)


# --------------------------------------------------------------------------- #
# Stealth init script                                                         #
# --------------------------------------------------------------------------- #
def _build_stealth_script(persona: _Persona) -> str:
    """Build the JS injected into every new document.

    Patches the most-fingerprinted vectors. Not a full anti-bot solution
    (those need ``tf-playwright-stealth`` or similar), but enough to defeat
    the cheap detectors that flag fresh Playwright sessions.
    """
    primary = persona.locale
    base = primary.split("-", 1)[0]
    langs = [primary] if primary == base else [primary, base]
    js_langs = "[" + ",".join(f"'{lang}'" for lang in langs) + "]"

    # Hardware concurrency / device memory: typical user values, not the
    # default Playwright values which can stand out on certain hosts.
    hw_concurrency = random.choice([4, 8, 8, 12, 16])
    device_memory = random.choice([4, 8, 8, 16])

    return f"""
    // 1. Hide the webdriver flag.
    Object.defineProperty(Navigator.prototype, 'webdriver', {{
        get: () => undefined,
        configurable: true,
    }});

    // 2. navigator.languages matches the persona locale.
    Object.defineProperty(Navigator.prototype, 'languages', {{
        get: () => {js_langs},
        configurable: true,
    }});

    // 3. Non-empty plugins / mimeTypes arrays (headless Chromium reports []).
    Object.defineProperty(Navigator.prototype, 'plugins', {{
        get: () => {{
            const fake = [1, 2, 3, 4, 5];
            fake.item = (i) => fake[i];
            fake.namedItem = () => null;
            fake.refresh = () => undefined;
            return fake;
        }},
        configurable: true,
    }});

    // 4. window.chrome shim for non-Edge Chromium personas.
    if (!window.chrome) {{
        window.chrome = {{
            runtime: {{}},
            csi: () => {{}},
            loadTimes: () => {{}},
            app: {{ isInstalled: false }},
        }};
    }}

    // 5. Permissions API consistency: Notification.permission must match
    //    permissions.query({{name:'notifications'}}). Detectors check this.
    const _origQuery = window.navigator.permissions && window.navigator.permissions.query;
    if (_origQuery) {{
        window.navigator.permissions.query = (parameters) => (
            parameters && parameters.name === 'notifications'
                ? Promise.resolve({{ state: Notification.permission }})
                : _origQuery.call(window.navigator.permissions, parameters)
        );
    }}

    // 6. WebGL vendor/renderer commonly leak "SwiftShader" / "Google Inc."
    //    in headless. Spoof to look like a real GPU.
    try {{
        const _getParam = WebGLRenderingContext.prototype.getParameter;
        WebGLRenderingContext.prototype.getParameter = function (parameter) {{
            // UNMASKED_VENDOR_WEBGL = 37445, UNMASKED_RENDERER_WEBGL = 37446
            if (parameter === 37445) return 'Intel Inc.';
            if (parameter === 37446) return 'Intel Iris OpenGL Engine';
            return _getParam.apply(this, [parameter]);
        }};
    }} catch (e) {{ /* WebGL not available - ignore */ }}

    // 7. hardwareConcurrency / deviceMemory: typical user values.
    Object.defineProperty(Navigator.prototype, 'hardwareConcurrency', {{
        get: () => {hw_concurrency},
        configurable: true,
    }});
    Object.defineProperty(Navigator.prototype, 'deviceMemory', {{
        get: () => {device_memory},
        configurable: true,
    }});

    // 8. Strip the iframe.contentWindow detection trick (chrome-headless quirk).
    try {{
        const _origDesc = Object.getOwnPropertyDescriptor(
            HTMLIFrameElement.prototype, 'contentWindow'
        );
        if (_origDesc && _origDesc.get) {{
            Object.defineProperty(HTMLIFrameElement.prototype, 'contentWindow', {{
                get: function () {{ return _origDesc.get.call(this); }},
                configurable: true,
            }});
        }}
    }} catch (e) {{ /* ignore */ }}
    """


# --------------------------------------------------------------------------- #
# Persona / backoff helpers (module-level so they're easy to unit test)       #
# --------------------------------------------------------------------------- #
def _pick_persona(rng: random.Random | None = None) -> _Persona:
    """Choose a random persona. ``rng`` injectable for deterministic tests."""
    return (rng or random).choice(_PERSONAS)


def _compute_backoff_ms(
    attempt: int,
    *,
    base_ms: int,
    max_ms: int,
    rng: random.Random | None = None,
) -> int:
    """Exponential backoff with 0-30% jitter, capped at ``max_ms``.

    ``attempt`` is 0-indexed (first retry passes 0).
    """
    rand = rng or random
    exp_delay = min(base_ms * (2**attempt), max_ms)
    jitter = rand.uniform(0, exp_delay * 0.3)
    return int(exp_delay + jitter)


def _parse_proxy_url(raw: str) -> dict[str, str]:
    """Convert a ``http://user:pass@host:port`` URL into Playwright's proxy dict.

    Playwright wants ``{"server": "...", "username": "...", "password": "..."}``;
    the URL form is what users put in ``.env``. Username / password are split
    out so they're not visible in the ``server`` field's basic auth segment.
    """
    from urllib.parse import urlparse

    parsed = urlparse(raw)
    if not parsed.scheme or not parsed.hostname:
        raise ValueError(f"invalid brave_proxy URL: {raw!r}")

    server = f"{parsed.scheme}://{parsed.hostname}"
    if parsed.port:
        server = f"{server}:{parsed.port}"
    out: dict[str, str] = {"server": server}
    if parsed.username:
        out["username"] = parsed.username
    if parsed.password:
        out["password"] = parsed.password
    return out


# --------------------------------------------------------------------------- #
# Provider                                                                    #
# --------------------------------------------------------------------------- #
class BraveSearchProvider(SearchProvider):
    """Search backed by ``https://search.brave.com/search``."""

    name: ClassVar[str] = "brave"
    SEARCH_URL: ClassVar[str] = "https://search.brave.com/search"
    HOMEPAGE_URL: ClassVar[str] = "https://search.brave.com/"

    # Selectors for the homepage search input. Brave has changed these over
    # time, so we keep a small fallback chain.
    _SEARCH_INPUT_SELECTORS: ClassVar[tuple[str, ...]] = (
        "input#searchbox",
        'input[name="q"]',
        'input[type="search"]',
        'textarea[name="q"]',
    )

    def __init__(self, browser: BrowserManager, settings: Settings) -> None:
        super().__init__(browser=browser, settings=settings)
        # Per-persona Cloudflare/session cookie cache. Populated after a
        # successful flow and replayed on subsequent requests. Eviction
        # happens on 429 (cookies are poisoned).
        self._persona_state: dict[_Persona, dict] = {}
        # Guards cache reads/writes against concurrent searches.
        self._state_lock = asyncio.Lock()

    async def search(self, query: str, *, max_results: int) -> list[SearchResult]:
        limit = self._clamp(max_results)
        attempts = self._settings.brave_retry_attempts
        logger.info(
            "brave.search", extra={"query": query, "limit": limit, "max_attempts": attempts}
        )

        last_exc: ProviderBlockedError | None = None
        used_personas: set[_Persona] = set()
        for attempt in range(attempts):
            # Try to use a persona we haven't burned this call.
            persona = self._pick_fresh_persona(used_personas)
            used_personas.add(persona)
            try:
                return await self._search_once(query, limit=limit, persona=persona)
            except ProviderBlockedError as exc:
                last_exc = exc
                # Evict the (now likely-poisoned) cookie state for this persona.
                async with self._state_lock:
                    self._persona_state.pop(persona, None)
                if attempt + 1 >= attempts:
                    break
                delay_ms = _compute_backoff_ms(
                    attempt,
                    base_ms=self._settings.brave_retry_backoff_base_ms,
                    max_ms=self._settings.brave_retry_backoff_max_ms,
                )
                logger.warning(
                    "brave blocked (%s); sleeping %dms before attempt %d/%d",
                    exc,
                    delay_ms,
                    attempt + 2,
                    attempts,
                )
                await asyncio.sleep(delay_ms / 1000)

        assert last_exc is not None
        raise last_exc

    def _pick_fresh_persona(self, exclude: set[_Persona]) -> _Persona:
        """Pick a persona we haven't tried this call, falling back to any if all used."""
        candidates = [p for p in _PERSONAS if p not in exclude]
        return random.choice(candidates) if candidates else _pick_persona()

    # ------------------------------------------------------------------ #
    # one search attempt                                                 #
    # ------------------------------------------------------------------ #
    async def _search_once(
        self, query: str, *, limit: int, persona: _Persona
    ) -> list[SearchResult]:
        await self._sleep_prenav_jitter()

        async with self._state_lock:
            cached_state = self._persona_state.get(persona)

        proxy = self._build_proxy_config()

        async with self._browser.new_context(
            user_agent=persona.user_agent,
            viewport=persona.viewport,
            locale=persona.locale,
            timezone_id=persona.timezone_id,
            extra_http_headers=persona.extra_http_headers,
            storage_state=cached_state,
            proxy=proxy,
        ) as ctx:
            await ctx.add_init_script(script=_build_stealth_script(persona))
            page = await ctx.new_page()

            try:
                if self._settings.brave_use_homepage_flow and cached_state is None:
                    # Cold path: warm the session through the real form.
                    await self._do_homepage_flow(page, query)
                else:
                    # Warm path (or homepage flow disabled): hit search URL
                    # directly. Cached cookies make this look like a returning
                    # user; without them it's a bare-bones request that 429s
                    # easily, but we honour the user's opt-out either way.
                    await self._navigate_search(page, query)
            except PlaywrightTimeoutError as exc:
                raise ProviderTimeoutError(
                    f"brave did not load within {self._settings.request_timeout_ms}ms"
                ) from exc
            except PlaywrightError as exc:
                raise ProviderUnavailableError(f"brave navigation failed: {exc}") from exc

            # Give the SERP a beat to settle. No results == legitimate empty
            # response, so suppress the timeout.
            with contextlib.suppress(PlaywrightTimeoutError):
                await page.wait_for_selector('div.snippet[data-type="web"]', timeout=5_000)

            # Tiny human-ish dwell before reading content. Best-effort.
            with contextlib.suppress(PlaywrightError, PlaywrightTimeoutError):
                await self._humanize(page)

            html = await page.content()

            if _looks_like_block(html):
                raise ProviderBlockedError("brave returned an anti-bot challenge")

            results = self.parse_html(html, max_results=limit, source=self.name)

            # Capture the fresh cookies *before* the context closes so the
            # next request for this persona can replay them.
            with contextlib.suppress(PlaywrightError):
                state = await ctx.storage_state()
                async with self._state_lock:
                    self._persona_state[persona] = state

        return results

    # ------------------------------------------------------------------ #
    # navigation strategies                                              #
    # ------------------------------------------------------------------ #
    async def _navigate_search(self, page: Page, query: str) -> None:
        """Go directly to ``/search?q=...``. Used in the warm path."""
        url = f"{self.SEARCH_URL}?q={quote_plus(query)}"
        response = await page.goto(url, wait_until="domcontentloaded")
        self._assert_response_ok(response, where="search")

    async def _do_homepage_flow(self, page: Page, query: str) -> None:
        """Homepage → click search box → type query → submit.

        This is the single most impactful behavioural change. Real users
        almost never paste ``/search?q=foo`` URLs; they land on the home page
        and use the form. Brave/Cloudflare scores that flow very differently.
        """
        response = await page.goto(self.HOMEPAGE_URL, wait_until="domcontentloaded")
        self._assert_response_ok(response, where="homepage")

        # Find the search input. Brave occasionally tweaks the markup, so try
        # a couple of selectors in order.
        input_handle = None
        for selector in self._SEARCH_INPUT_SELECTORS:
            with contextlib.suppress(PlaywrightTimeoutError):
                input_handle = await page.wait_for_selector(
                    selector, state="visible", timeout=4_000
                )
                if input_handle is not None:
                    break
        if input_handle is None:
            raise ProviderUnavailableError(
                "brave homepage did not expose a recognisable search input"
            )

        # Click into the input (focus event matters), pause briefly, then
        # type with realistic per-keystroke delays.
        await input_handle.click()
        await asyncio.sleep(random.uniform(0.15, 0.4))

        delay_lo = self._settings.brave_keystroke_min_ms
        delay_hi = max(self._settings.brave_keystroke_max_ms, delay_lo)
        # Playwright's `type(delay=...)` already adds a fixed per-key delay;
        # we add a tiny extra randomisation on top by typing in small chunks.
        for chunk in _chunk_for_typing(query):
            await page.keyboard.type(chunk, delay=random.uniform(delay_lo, delay_hi))
            # Occasional micro-pause between chunks, like a real person thinking.
            if random.random() < 0.3:
                await asyncio.sleep(random.uniform(0.05, 0.25))

        # Submit via Enter (more authentic than clicking the submit button).
        await page.keyboard.press("Enter")

        # Wait for the navigation to the SERP. ``wait_until="domcontentloaded"``
        # is enough; we further wait for the results selector downstream.
        # Sometimes Brave's JS submits via fetch without a real URL change, so
        # we suppress the timeout and let the SERP-selector wait handle it.
        with contextlib.suppress(PlaywrightTimeoutError):
            await page.wait_for_url("**/search?**", timeout=self._settings.request_timeout_ms)

        # The post-submit response status isn't directly available, so probe
        # the page: if the body contains the bot-gate needle we raise here.
        body_snippet = await page.content()
        if _looks_like_block(body_snippet):
            raise ProviderBlockedError("brave bot-gate after homepage submit")

    def _assert_response_ok(self, response, *, where: str) -> None:
        """Translate response status into our domain exceptions."""
        if response is None:
            raise ProviderUnavailableError(f"brave {where} returned no response")
        if response.status == 429:
            raise ProviderBlockedError(f"brave rate-limited the {where} request (429)")
        if response.status in (403, 503):
            # 403/503 from search.brave.com is almost always the Cloudflare gate.
            raise ProviderBlockedError(f"brave {where} returned HTTP {response.status}")
        if response.status >= 400:
            raise ProviderUnavailableError(f"brave {where} returned HTTP {response.status}")

    # ------------------------------------------------------------------ #
    # helpers                                                            #
    # ------------------------------------------------------------------ #
    def _build_proxy_config(self) -> dict[str, str] | None:
        raw = self._settings.brave_proxy
        if not raw:
            return None
        try:
            return _parse_proxy_url(raw)
        except ValueError:
            logger.warning("ignoring malformed brave_proxy=%r", raw)
            return None

    async def _sleep_prenav_jitter(self) -> None:
        lo = self._settings.brave_prenav_jitter_min_ms
        hi = self._settings.brave_prenav_jitter_max_ms
        if hi <= 0:
            return
        delay_ms = random.randint(lo, hi) if hi > lo else lo
        if delay_ms > 0:
            await asyncio.sleep(delay_ms / 1000)

    @staticmethod
    async def _humanize(page: Page) -> None:
        """Perform a couple of cheap, low-noise user-like gestures."""
        x = random.randint(120, 900)
        y = random.randint(120, 600)
        await page.mouse.move(x, y, steps=random.randint(5, 15))
        await page.mouse.wheel(0, random.randint(100, 350))
        await asyncio.sleep(random.uniform(0.15, 0.45))

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


# --------------------------------------------------------------------------- #
# Module-level helpers                                                        #
# --------------------------------------------------------------------------- #
def _chunk_for_typing(query: str) -> list[str]:
    """Split ``query`` into small chunks so typing has natural pauses.

    Real typists pause between words and after punctuation. We mostly type
    1-3 chars at a time, splitting on spaces so the rhythm has wider gaps
    around word boundaries.
    """
    if not query:
        return []
    chunks: list[str] = []
    cursor = 0
    n = len(query)
    while cursor < n:
        # Random chunk length: usually short, occasionally longer.
        step = random.choice([1, 1, 2, 2, 3])
        # Snap to a space boundary if one is very close, so we get natural
        # word-end pauses.
        next_space = query.find(" ", cursor, cursor + step + 2)
        end = next_space + 1 if 0 <= next_space <= cursor + step + 1 else cursor + step
        chunks.append(query[cursor:end])
        cursor = end
    return chunks


def _looks_like_block(html: str) -> bool:
    """Heuristic: detect Brave's bot/captcha gate."""
    needles = (
        "Are you human?",
        "captcha-bypass",
        "challenge-platform",
        "Just a moment",  # Cloudflare interstitial
        "cf-mitigated",
    )
    return any(needle in html for needle in needles)
