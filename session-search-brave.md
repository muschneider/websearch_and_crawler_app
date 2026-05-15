# Prompt

The search with brave is always returning the message:
brave rate-limited the request (429)

Can fix it with something to the search look like as human searching, like adding user-agent, random delay, etc. ?

# Brave search 429 rate limit fix

**Session ID:** ses_1d4907e4bffe5p1so1U9OvfinV
**Created:** 5/15/2026, 8:39:48 AM
**Updated:** 5/15/2026, 8:49:41 AM

---

## User

The search with brave is always returning the message:
brave rate-limited the request (429)

Can fix it with something to the search look like as human searching, like adding user-agent, random delay, etc. ?

---

## Assistant (Build · Claude Opus 4.7 · 5.8s)

_Thinking:_

I need to look at the codebase to understand how Brave search is currently implemented and where the rate limiting issue might be occurring.

**Tool: bash**

**Input:**

```json
{
  "command": "ls -la",
  "description": "List files in current directory"
}
```

**Output:**

```
total 496
drwxr-xr-x 8 mauro mauro   4096 mai 15 06:52 .
drwxr-xr-x 5 mauro mauro   4096 mai 11 05:43 ..
-rw-r--r-- 1 mauro mauro    882 mai 11 05:52 .env.example
-rw-r--r-- 1 mauro mauro  15244 mai 12 07:23 example.md
drwxr-xr-x 7 mauro mauro   4096 mai 12 08:41 .git
-rw-r--r-- 1 mauro mauro    348 mai 11 05:51 .gitignore
-rw-r--r-- 1 mauro mauro  13860 mai 12 10:52 langchain.md
-rw-r--r-- 1 mauro mauro   1281 mai 12 06:30 mise.toml
-rw-r--r-- 1 mauro mauro   2085 mai 12 06:47 pyproject.toml
drwxr-xr-x 3 mauro mauro   4096 mai 11 06:01 .pytest_cache
-rw-r--r-- 1 mauro mauro      5 mai 11 05:44 .python-version
-rw-r--r-- 1 mauro mauro  21671 mai 12 07:05 README.md
drwxr-xr-x 3 mauro mauro   4096 mai 11 06:03 .ruff_cache
-rw-r--r-- 1 mauro mauro 206958 mai 15 06:52 session-ses_1e9c.md
drwxr-xr-x 3 mauro mauro   4096 mai 11 05:52 src
drwxr-xr-x 4 mauro mauro   4096 mai 12 06:29 tests
-rw-r--r-- 1 mauro mauro 187685 mai 11 14:53 uv.lock
drwxr-xr-x 5 mauro mauro   4096 mai 11 06:00 .venv

```

---

## Assistant (Build · Claude Opus 4.7 · 6.2s)

**Tool: bash**

**Input:**

```json
{
  "command": "find src -type f -name \"*.py\" | head -50",
  "description": "Find Python files in src"
}
```

**Output:**

```
src/websearch_api/extractors/__init__.py
src/websearch_api/extractors/page.py
src/websearch_api/config.py
src/websearch_api/__main__.py
src/websearch_api/logging_config.py
src/websearch_api/api/dependencies.py
src/websearch_api/api/routes.py
src/websearch_api/api/__init__.py
src/websearch_api/main.py
src/websearch_api/models.py
src/websearch_api/__init__.py
src/websearch_api/exceptions.py
src/websearch_api/providers/brave.py
src/websearch_api/providers/duckduckgo.py
src/websearch_api/providers/__init__.py
src/websearch_api/providers/base.py
src/websearch_api/browser/manager.py
src/websearch_api/browser/__init__.py

```

---

## Assistant (Build · Claude Opus 4.7 · 4.0s)

**Tool: read**

**Input:**

```json
{
  "filePath": "/home/mauro/ws/dev/AI/websearch_api/src/websearch_api/providers/brave.py"
}
```

**Output:**

```
<path>/home/mauro/ws/dev/AI/websearch_api/src/websearch_api/providers/brave.py</path>
<type>file</type>
<content>
1: """Brave Search provider.
2:
3: Brave Search (``search.brave.com``) ships a server-rendered HTML SERP that is
4: friendly to ``Playwright``-driven scraping: the result cards are present in
5: the initial HTML, no captcha gate, no SPA hydration required.
6:
7: Layout (as of 2025-2026)::
8:
9:     <div class="snippet" data-type="web">
10:       <div class="result-wrapper">
11:         <div class="result-content">
12:           <a href="https://target/url">
13:             <cite class="snippet-url">target.url</cite>
14:             <div class="title search-snippet-title">Page Title</div>
15:           </a>
16:           <div class="generic-snippet">
17:             <div class="content">snippet body...</div>
18:           </div>
19:         </div>
20:       </div>
21:     </div>
22:
23: If Brave ever changes its DOM only :meth:`parse_html` needs to be updated.
24: """
25:
26: from __future__ import annotations
27:
28: import contextlib
29: import logging
30: from typing import ClassVar
31: from urllib.parse import quote_plus
32:
33: from bs4 import BeautifulSoup
34: from playwright.async_api import Error as PlaywrightError
35: from playwright.async_api import TimeoutError as PlaywrightTimeoutError
36: from pydantic import AnyHttpUrl, ValidationError
37:
38: from websearch_api.exceptions import (
39:     ProviderBlockedError,
40:     ProviderTimeoutError,
41:     ProviderUnavailableError,
42: )
43: from websearch_api.models import SearchResult
44: from websearch_api.providers.base import SearchProvider
45:
46: logger = logging.getLogger(__name__)
47:
48:
49: class BraveSearchProvider(SearchProvider):
50:     """Search backed by ``https://search.brave.com/search``."""
51:
52:     name: ClassVar[str] = "brave"
53:     SEARCH_URL: ClassVar[str] = "https://search.brave.com/search"
54:
55:     async def search(self, query: str, *, max_results: int) -> list[SearchResult]:
56:         limit = self._clamp(max_results)
57:         logger.info("brave.search", extra={"query": query, "limit": limit})
58:
59:         url = f"{self.SEARCH_URL}?q={quote_plus(query)}"
60:         async with self._browser.new_context() as ctx:
61:             page = await ctx.new_page()
62:             try:
63:                 response = await page.goto(url, wait_until="domcontentloaded")
64:             except PlaywrightTimeoutError as exc:
65:                 raise ProviderTimeoutError(
66:                     f"brave did not load within {self._settings.request_timeout_ms}ms"
67:                 ) from exc
68:             except PlaywrightError as exc:
69:                 raise ProviderUnavailableError(f"brave navigation failed: {exc}") from exc
70:
71:             if response is None:
72:                 raise ProviderUnavailableError("brave returned no response")
73:             if response.status == 429:
74:                 raise ProviderBlockedError("brave rate-limited the request (429)")
75:             if response.status >= 400:
76:                 raise ProviderUnavailableError(f"brave returned HTTP {response.status}")
77:
78:             # Give the Svelte app a brief moment to finish hydration; the SERP
79:             # cards are already in the initial HTML, but a small settle helps
80:             # when Brave inlines lazy snippets. No results = legitimate empty response.
81:             with contextlib.suppress(PlaywrightTimeoutError):
82:                 await page.wait_for_selector('div.snippet[data-type="web"]', timeout=5_000)
83:
84:             html = await page.content()
85:
86:         if _looks_like_block(html):
87:             raise ProviderBlockedError("brave returned an anti-bot challenge")
88:
89:         return self.parse_html(html, max_results=limit, source=self.name)
90:
91:     # ------------------------------------------------------------------ #
92:     # Pure parser - unit-testable without a browser                      #
93:     # ------------------------------------------------------------------ #
94:     @staticmethod
95:     def parse_html(html: str, *, max_results: int, source: str = "brave") -> list[SearchResult]:
96:         """Parse a Brave SERP into structured ``SearchResult`` rows."""
97:         soup = BeautifulSoup(html, "lxml")
98:         results: list[SearchResult] = []
99:
100:         for block in soup.select('div.snippet[data-type="web"]'):
101:             link = block.select_one("a[href^=http]")
102:             if link is None:
103:                 continue
104:             href = link.get("href") or ""
105:
106:             title_el = block.select_one(
107:                 "div.title.search-snippet-title, div.title, .search-snippet-title"
108:             )
109:             if title_el is None:
110:                 # Fall back to the anchor's site-name label if no dedicated title.
111:                 title_el = block.select_one(".site-name-content .text-ellipsis")
112:             title = title_el.get_text(" ", strip=True) if title_el else ""
113:
114:             snippet_el = block.select_one("div.generic-snippet .content, div.snippet-content")
115:             snippet = snippet_el.get_text(" ", strip=True) if snippet_el else None
116:
117:             cite_el = block.select_one("cite.snippet-url, cite")
118:             metadata: dict[str, str] = {}
119:             if cite_el:
120:                 metadata["displayed_url"] = cite_el.get_text(" ", strip=True)
121:
122:             try:
123:                 results.append(
124:                     SearchResult(
125:                         title=title or href,
126:                         url=AnyHttpUrl(href),
127:                         snippet=snippet,
128:                         rank=len(results) + 1,
129:                         source=source,
130:                         metadata=metadata,
131:                     )
132:                 )
133:             except ValidationError:
134:                 logger.debug("skipping malformed brave result href=%r", href)
135:                 continue
136:
137:             if len(results) >= max_results:
138:                 break
139:
140:         return results
141:
142:
143: def _looks_like_block(html: str) -> bool:
144:     """Heuristic: detect Brave's bot/captcha gate."""
145:     needles = (
146:         "Are you human?",
147:         "captcha-bypass",
148:         "challenge-platform",
149:     )
150:     return any(needle in html for needle in needles)

(End of file - total 150 lines)
</content>
```

---

## Assistant (Build · Claude Opus 4.7 · 3.7s)

**Tool: read**

**Input:**

```json
{
  "filePath": "/home/mauro/ws/dev/AI/websearch_api/src/websearch_api/browser/manager.py"
}
```

**Output:**

```
<path>/home/mauro/ws/dev/AI/websearch_api/src/websearch_api/browser/manager.py</path>
<type>file</type>
<content>
1: """Process-wide Playwright lifecycle.
2:
3: Starting Chromium costs ~300-800 ms and consumes meaningful memory. We therefore
4: launch a **single** browser instance for the lifetime of the FastAPI process and
5: hand out fresh :class:`~playwright.async_api.BrowserContext` objects per request.
6: Contexts are cheap to create, fully isolate cookies/storage, and let us tune
7: viewport, user agent, and locale on a per-call basis.
8:
9: The manager is safe to use from multiple concurrent requests because each call
10: to :meth:`new_context` returns an independent context.
11: """
12:
13: from __future__ import annotations
14:
15: import logging
16: from collections.abc import AsyncIterator
17: from contextlib import asynccontextmanager
18: from typing import TYPE_CHECKING
19:
20: from playwright.async_api import Browser, Playwright, async_playwright
21:
22: from websearch_api.config import Settings
23:
24: if TYPE_CHECKING:
25:     from playwright.async_api import BrowserContext
26:
27: logger = logging.getLogger(__name__)
28:
29:
30: class BrowserManager:
31:     """Owns the Playwright + Chromium process for the app's lifetime."""
32:
33:     def __init__(self, settings: Settings) -> None:
34:         self._settings = settings
35:         self._playwright: Playwright | None = None
36:         self._browser: Browser | None = None
37:
38:     # ------------------------------------------------------------------ #
39:     # lifecycle                                                          #
40:     # ------------------------------------------------------------------ #
41:     async def start(self) -> None:
42:         """Launch Playwright + Chromium. Safe to call multiple times (no-op)."""
43:         if self._browser is not None:
44:             return
45:
46:         logger.info("starting playwright + chromium (headless=%s)", self._settings.browser_headless)
47:         self._playwright = await async_playwright().start()
48:         self._browser = await self._playwright.chromium.launch(
49:             headless=self._settings.browser_headless,
50:             args=[
51:                 "--disable-blink-features=AutomationControlled",
52:                 "--disable-dev-shm-usage",
53:             ],
54:         )
55:         logger.info("chromium ready: %s", self._browser.version)
56:
57:     async def stop(self) -> None:
58:         """Tear everything down. Safe to call when already stopped."""
59:         if self._browser is not None:
60:             try:
61:                 await self._browser.close()
62:             except Exception:  # pragma: no cover - best-effort shutdown
63:                 logger.warning("error closing browser", exc_info=True)
64:             self._browser = None
65:
66:         if self._playwright is not None:
67:             try:
68:                 await self._playwright.stop()
69:             except Exception:  # pragma: no cover
70:                 logger.warning("error stopping playwright", exc_info=True)
71:             self._playwright = None
72:
73:         logger.info("browser stopped")
74:
75:     # ------------------------------------------------------------------ #
76:     # introspection                                                      #
77:     # ------------------------------------------------------------------ #
78:     @property
79:     def is_ready(self) -> bool:
80:         return self._browser is not None and self._browser.is_connected()
81:
82:     # ------------------------------------------------------------------ #
83:     # context factory                                                    #
84:     # ------------------------------------------------------------------ #
85:     @asynccontextmanager
86:     async def new_context(
87:         self,
88:         *,
89:         locale: str = "en-US",
90:         viewport: tuple[int, int] = (1366, 768),
91:     ) -> AsyncIterator[BrowserContext]:
92:         """Yield a fresh isolated browser context, then close it.
93:
94:         Usage::
95:
96:             async with browser_manager.new_context() as ctx:
97:                 page = await ctx.new_page()
98:                 await page.goto(...)
99:         """
100:         if self._browser is None:
101:             raise RuntimeError("BrowserManager.start() must be called before new_context()")
102:
103:         context = await self._browser.new_context(
104:             user_agent=self._settings.user_agent,
105:             viewport={"width": viewport[0], "height": viewport[1]},
106:             locale=locale,
107:             ignore_https_errors=True,
108:         )
109:         # Reasonable default; individual goto/wait calls can still override.
110:         context.set_default_timeout(self._settings.request_timeout_ms)
111:         try:
112:             yield context
113:         finally:
114:             try:
115:                 await context.close()
116:             except Exception:  # pragma: no cover
117:                 logger.debug("error closing context", exc_info=True)

(End of file - total 117 lines)
</content>
```

---

## Assistant (Build · Claude Opus 4.7 · 5.1s)

**Tool: read**

**Input:**

```json
{
  "filePath": "/home/mauro/ws/dev/AI/websearch_api/src/websearch_api/config.py"
}
```

**Output:**

```
<path>/home/mauro/ws/dev/AI/websearch_api/src/websearch_api/config.py</path>
<type>file</type>
<content>
1: """Application configuration loaded from environment variables / .env."""
2:
3: from __future__ import annotations
4:
5: from functools import lru_cache
6: from typing import Annotated, Literal
7:
8: from pydantic import Field, field_validator
9: from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
10:
11:
12: class Settings(BaseSettings):
13:     """All runtime configuration for the service.
14:
15:     Values are read (in order of precedence) from:
16:       1. Process environment variables prefixed with ``WEBSEARCH_``
17:       2. A local ``.env`` file at the project root
18:       3. The defaults defined here
19:     """
20:
21:     model_config = SettingsConfigDict(
22:         env_prefix="WEBSEARCH_",
23:         env_file=".env",
24:         env_file_encoding="utf-8",
25:         case_sensitive=False,
26:         extra="ignore",
27:     )
28:
29:     # --- HTTP server ---
30:     host: str = "0.0.0.0"
31:     port: int = 8000
32:
33:     # --- Logging ---
34:     log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
35:     log_format: Literal["text", "json"] = "text"
36:
37:     # --- Browser ---
38:     browser_headless: bool = True
39:     request_timeout_ms: int = Field(default=20_000, ge=1_000, le=120_000)
40:     user_agent: str = (
41:         "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
42:         "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
43:     )
44:
45:     # --- Search defaults ---
46:     default_max_results: int = Field(default=10, ge=1, le=100)
47:     max_results_hard_cap: int = Field(default=50, ge=1, le=200)
48:
49:     # --- API ---
50:     # ``NoDecode`` tells pydantic-settings not to try ``json.loads`` on this
51:     # field, so we can accept a plain comma-separated string from the env.
52:     cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["*"])
53:
54:     @field_validator("cors_origins", mode="before")
55:     @classmethod
56:     def _split_cors(cls, value: object) -> object:
57:         """Allow ``WEBSEARCH_CORS_ORIGINS`` to be a comma-separated string in env."""
58:         if isinstance(value, str):
59:             return [origin.strip() for origin in value.split(",") if origin.strip()]
60:         return value
61:
62:     @field_validator("max_results_hard_cap")
63:     @classmethod
64:     def _hard_cap_gte_default(cls, value: int, info) -> int:
65:         default = info.data.get("default_max_results", 10)
66:         if value < default:
67:             raise ValueError(
68:                 f"max_results_hard_cap must be >= default_max_results (got {value} < {default})"
69:             )
70:         return value
71:
72:
73: @lru_cache(maxsize=1)
74: def get_settings() -> Settings:
75:     """Return a cached singleton ``Settings`` instance.
76:
77:     Cached so that environment is read once per process. Tests can clear the cache
78:     via ``get_settings.cache_clear()`` to inject fresh values.
79:     """
80:     return Settings()

(End of file - total 80 lines)
</content>
```

---

## Assistant (Build · Claude Opus 4.7 · 3.2s)

**Tool: read**

**Input:**

```json
{
  "filePath": "/home/mauro/ws/dev/AI/websearch_api/src/websearch_api/providers/base.py"
}
```

**Output:**

```
<path>/home/mauro/ws/dev/AI/websearch_api/src/websearch_api/providers/base.py</path>
<type>file</type>
<content>
1: """Abstract base class shared by every search provider."""
2:
3: from __future__ import annotations
4:
5: from abc import ABC, abstractmethod
6: from typing import ClassVar
7:
8: from websearch_api.browser.manager import BrowserManager
9: from websearch_api.config import Settings
10: from websearch_api.models import SearchResult
11:
12:
13: class SearchProvider(ABC):
14:     """Contract every search backend must implement.
15:
16:     Subclasses should keep their HTML parsing in a **pure static method** so it
17:     can be unit-tested with fixture data, with no live browser required.
18:     """
19:
20:     #: Unique slug used in the API (``provider="duckduckgo"`` etc).
21:     name: ClassVar[str]
22:
23:     def __init__(self, browser: BrowserManager, settings: Settings) -> None:
24:         self._browser = browser
25:         self._settings = settings
26:
27:     @abstractmethod
28:     async def search(self, query: str, *, max_results: int) -> list[SearchResult]:
29:         """Execute ``query`` and return up to ``max_results`` structured rows."""
30:         raise NotImplementedError
31:
32:     # ------------------------------------------------------------------ #
33:     # helpers shared by concrete providers                               #
34:     # ------------------------------------------------------------------ #
35:     def _clamp(self, requested: int | None) -> int:
36:         """Apply server-side caps to a caller-supplied ``max_results``."""
37:         default = self._settings.default_max_results
38:         cap = self._settings.max_results_hard_cap
39:         return min(requested or default, cap)

(End of file - total 39 lines)
</content>
```

---

## Assistant (Build · Claude Opus 4.7 · 4.6s)

_Thinking:_

Now I'm looking at the existing test suite to understand how brave is currently being tested.

**Tool: bash**

**Input:**

```json
{
  "command": "find tests -type f -name \"*.py\"",
  "description": "Find test files"
}
```

**Output:**

```
tests/test_providers_brave.py
tests/test_extractor.py
tests/conftest.py
tests/test_api.py
tests/test_providers_duckduckgo.py
tests/test_config.py
tests/__init__.py

```

---

## Assistant (Build · Claude Opus 4.7 · 3.6s)

**Tool: read**

**Input:**

```json
{
  "filePath": "/home/mauro/ws/dev/AI/websearch_api/tests/test_providers_brave.py"
}
```

**Output:**

```
<path>/home/mauro/ws/dev/AI/websearch_api/tests/test_providers_brave.py</path>
<type>file</type>
<content>
1: """Unit tests for the Brave Search provider's pure parser."""
2:
3: from __future__ import annotations
4:
5: from pathlib import Path
6:
7: import pytest
8:
9: from websearch_api.providers.brave import BraveSearchProvider, _looks_like_block
10:
11: FIXTURES_DIR = Path(__file__).parent / "fixtures"
12:
13:
14: @pytest.fixture
15: def brave_results_html() -> str:
16:     return (FIXTURES_DIR / "brave_results.html").read_text(encoding="utf-8")
17:
18:
19: def test_parse_html_extracts_web_results(brave_results_html: str) -> None:
20:     results = BraveSearchProvider.parse_html(brave_results_html, max_results=10)
21:
22:     # 3 organic web results in the fixture. The news card and the malformed
23:     # web card without an anchor are both skipped.
24:     assert len(results) == 3
25:     titles = [r.title for r in results]
26:     assert titles == [
27:         "FastAPI",
28:         "Using FastAPI to Build Python Web APIs - Real Python",
29:         "tiangolo/fastapi - GitHub",
30:     ]
31:
32:     first = results[0]
33:     assert str(first.url) == "https://fastapi.tiangolo.com/"
34:     assert first.snippet is not None
35:     assert "FastAPI is a modern, fast" in first.snippet
36:     assert first.rank == 1
37:     assert first.source == "brave"
38:     assert first.metadata.get("displayed_url") == "fastapi.tiangolo.com"
39:
40:
41: def test_parse_html_honours_max_results(brave_results_html: str) -> None:
42:     results = BraveSearchProvider.parse_html(brave_results_html, max_results=2)
43:     assert len(results) == 2
44:     assert [r.rank for r in results] == [1, 2]
45:
46:
47: def test_parse_html_returns_empty_for_no_results() -> None:
48:     assert BraveSearchProvider.parse_html("<html></html>", max_results=10) == []
49:
50:
51: def test_looks_like_block_detects_captcha() -> None:
52:     assert _looks_like_block("<html>Are you human? please verify...</html>") is True
53:     assert _looks_like_block("<html>normal content</html>") is False
54:
55:
56: def test_results_are_sequentially_ranked(brave_results_html: str) -> None:
57:     results = BraveSearchProvider.parse_html(brave_results_html, max_results=10)
58:     assert [r.rank for r in results] == list(range(1, len(results) + 1))

(End of file - total 58 lines)
</content>
```

---

## Assistant (Build · Claude Opus 4.7 · 3.3s)

**Tool: read**

**Input:**

```json
{
  "filePath": "/home/mauro/ws/dev/AI/websearch_api/src/websearch_api/providers/duckduckgo.py"
}
```

**Output:**

```
<path>/home/mauro/ws/dev/AI/websearch_api/src/websearch_api/providers/duckduckgo.py</path>
<type>file</type>
<content>
1: """DuckDuckGo search provider.
2:
3: We target the lightweight HTML endpoint at ``html.duckduckgo.com/html`` because:
4:
5: * It server-renders results - no JS execution required, so the parse is robust.
6: * It does not deploy a captcha for normal traffic.
7: * The DOM layout has been stable for years: ``div.result`` blocks containing
8:   an ``a.result__a`` anchor and an ``a.result__snippet`` body.
9:
10: If DuckDuckGo eventually changes the layout we only need to tweak
11: :meth:`DuckDuckGoProvider.parse_html`.
12: """
13:
14: from __future__ import annotations
15:
16: import logging
17: from typing import ClassVar
18: from urllib.parse import parse_qs, unquote, urlparse
19:
20: from bs4 import BeautifulSoup
21: from playwright.async_api import Error as PlaywrightError
22: from playwright.async_api import TimeoutError as PlaywrightTimeoutError
23: from pydantic import AnyHttpUrl, ValidationError
24:
25: from websearch_api.exceptions import (
26:     ProviderBlockedError,
27:     ProviderTimeoutError,
28:     ProviderUnavailableError,
29: )
30: from websearch_api.models import SearchResult
31: from websearch_api.providers.base import SearchProvider
32:
33: logger = logging.getLogger(__name__)
34:
35:
36: class DuckDuckGoProvider(SearchProvider):
37:     """Search backed by ``https://html.duckduckgo.com/html/``."""
38:
39:     name: ClassVar[str] = "duckduckgo"
40:     SEARCH_URL: ClassVar[str] = "https://html.duckduckgo.com/html/"
41:
42:     async def search(self, query: str, *, max_results: int) -> list[SearchResult]:
43:         limit = self._clamp(max_results)
44:         logger.info("ddg.search", extra={"query": query, "limit": limit})
45:
46:         async with self._browser.new_context() as ctx:
47:             page = await ctx.new_page()
48:             try:
49:                 await page.goto(
50:                     f"{self.SEARCH_URL}?q={query}",
51:                     wait_until="domcontentloaded",
52:                 )
53:                 # The "no results" page also renders fast, so we cap the wait
54:                 # rather than wait_for_selector which would error on empty SERPs.
55:                 await page.wait_for_load_state("networkidle", timeout=5_000)
56:             except PlaywrightTimeoutError as exc:
57:                 raise ProviderTimeoutError(
58:                     f"duckduckgo did not load within {self._settings.request_timeout_ms}ms"
59:                 ) from exc
60:             except PlaywrightError as exc:
61:                 raise ProviderUnavailableError(f"duckduckgo navigation failed: {exc}") from exc
62:
63:             html = await page.content()
64:
65:         if "Unfortunately, bots use DuckDuckGo too" in html or "anomaly-modal" in html:
66:             raise ProviderBlockedError("duckduckgo presented an anti-bot challenge")
67:
68:         return self.parse_html(html, max_results=limit, source=self.name)
69:
70:     # ------------------------------------------------------------------ #
71:     # Pure parser - unit-testable without a browser                      #
72:     # ------------------------------------------------------------------ #
73:     @staticmethod
74:     def parse_html(
75:         html: str, *, max_results: int, source: str = "duckduckgo"
76:     ) -> list[SearchResult]:
77:         """Parse DuckDuckGo HTML SERP into structured ``SearchResult`` rows.
78:
79:         Returns an empty list when the SERP renders no results - callers should
80:         treat that as a successful-but-empty response.
81:         """
82:         soup = BeautifulSoup(html, "lxml")
83:         results: list[SearchResult] = []
84:
85:         for rank, block in enumerate(soup.select("div.result"), start=1):
86:             if "result--ad" in (block.get("class") or []):
87:                 # Skip sponsored results so callers get the organic top N.
88:                 continue
89:
90:             anchor = block.select_one("a.result__a")
91:             if anchor is None:
92:                 continue
93:
94:             title = anchor.get_text(strip=True)
95:             href = anchor.get("href") or ""
96:             url = _clean_ddg_url(href)
97:             if not url:
98:                 continue
99:
100:             snippet_el = block.select_one("a.result__snippet, .result__snippet")
101:             snippet = snippet_el.get_text(" ", strip=True) if snippet_el else None
102:
103:             metadata: dict[str, str] = {}
104:             displayed_url_el = block.select_one(".result__url")
105:             if displayed_url_el:
106:                 displayed = displayed_url_el.get_text(" ", strip=True)
107:                 if displayed:
108:                     metadata["displayed_url"] = displayed
109:
110:             try:
111:                 results.append(
112:                     SearchResult(
113:                         title=title or url,
114:                         url=AnyHttpUrl(url),
115:                         snippet=snippet,
116:                         rank=len(results) + 1,
117:                         source=source,
118:                         metadata=metadata,
119:                     )
120:                 )
121:             except ValidationError:
122:                 logger.debug("skipping malformed ddg result at rank %d (url=%r)", rank, url)
123:                 continue
124:
125:             if len(results) >= max_results:
126:                 break
127:
128:         return results
129:
130:
131: def _clean_ddg_url(href: str) -> str | None:
132:     """DuckDuckGo wraps external links via ``//duckduckgo.com/l/?uddg=<encoded>``.
133:
134:     Strip the redirect and decode the real target. Returns ``None`` for empty,
135:     relative-only, or otherwise unusable hrefs.
136:     """
137:     if not href:
138:         return None
139:
140:     # Normalise schemeless ``//`` URLs.
141:     if href.startswith("//"):
142:         href = "https:" + href
143:
144:     parsed = urlparse(href)
145:     if parsed.netloc.endswith("duckduckgo.com") and parsed.path in {"/l/", "/l"}:
146:         qs = parse_qs(parsed.query)
147:         target = qs.get("uddg", [""])[0]
148:         if target:
149:             return unquote(target)
150:
151:     if parsed.scheme in {"http", "https"} and parsed.netloc:
152:         return href
153:
154:     return None

(End of file - total 154 lines)
</content>
```

---

## Assistant (Build · Claude Opus 4.7 · 3.8s)

**Tool: read**

**Input:**

```json
{
  "filePath": "/home/mauro/ws/dev/AI/websearch_api/.env.example"
}
```

**Output:**

```
<path>/home/mauro/ws/dev/AI/websearch_api/.env.example</path>
<type>file</type>
<content>
1: # Copy to `.env` and adjust as needed. Every key is optional; sane defaults ship in code.
2:
3: # --- HTTP server ---
4: WEBSEARCH_HOST=0.0.0.0
5: WEBSEARCH_PORT=8000
6:
7: # --- Logging ---
8: # One of DEBUG, INFO, WARNING, ERROR, CRITICAL
9: WEBSEARCH_LOG_LEVEL=INFO
10: # "json" for structured one-line-per-record output, "text" for human-readable
11: WEBSEARCH_LOG_FORMAT=text
12:
13: # --- Browser ---
14: # Set to "false" to watch a real browser window while debugging selectors
15: WEBSEARCH_BROWSER_HEADLESS=true
16: # Per-request navigation timeout in milliseconds
17: WEBSEARCH_REQUEST_TIMEOUT_MS=20000
18: # Optional override for the User-Agent string used by the browser
19: # WEBSEARCH_USER_AGENT="Mozilla/5.0 ..."
20:
21: # --- Search defaults ---
22: WEBSEARCH_DEFAULT_MAX_RESULTS=10
23: WEBSEARCH_MAX_RESULTS_HARD_CAP=50
24:
25: # --- API surface ---
26: # Comma-separated list of origins allowed by CORS. Use "*" to allow any.
27: WEBSEARCH_CORS_ORIGINS=*

(End of file - total 27 lines)
</content>
```

---

## Assistant (Build · Claude Opus 4.7 · 223.1s)

_Thinking:_

I'm identifying the root causes of the Brave 429 blocking—the static User-Agent screams bot, and there's no header randomization, request delays, or retry logic with backoff. I need to implement several humanization strategies starting with rotating User-Agents across different browsers and operating systems.

For the browser context, I should randomize viewport dimensions, locale, and timezone while setting realistic headers like Accept-Language and Referer to mimic genuine user behavior. I'll also need stealth measures to hide Playwright detection signals and add human-like delays before navigation. Since they're asking specifically about adding User-Agent rotation and random delays, I should clarify whether they want me to use the playwright-stealth library or build a custom solution. Actually, let me re-read what they're asking for. They want it to look human—user-agent rotation, random delays, that kind of thing. The playwright-stealth library would be more comprehensive, but they're already hinting at a custom approach. I think the best move is to ask one clear question about whether they'd prefer a dependency or rolling it ourselves, then implement based on their preference.

I've analyzed the codebase. The 429s from Brave are happening because the current setup is very easy to fingerprint as a bot:

- A single static User-Agent (Chrome 124 on Linux, now ~2 years old)
- Fixed viewport (1366×768), no randomization
- No `Accept-Language` / `Sec-CH-UA-*` client hints
- No `Referer`
- `navigator.webdriver` is still `true` (only `--disable-blink-features=AutomationControlled` is set)
- No jitter between requests, no retry on 429
- No per-host rate limiting

Before I write code, one quick decision:

**Tool: question**

**Input:**

```json
{
  "questions": [
    {
      "question": "How aggressive should the anti-bot evasion be? This shapes scope and dependencies.",
      "header": "Evasion strategy",
      "options": [
        {
          "label": "Custom + retry only (Recommended)",
          "description": "Rotate UA/viewport/locale, add realistic headers (Accept-Language, Sec-CH-UA, Referer), small navigator.webdriver patch via init_script, random pre-nav jitter, 429-aware retry with exponential backoff. No new dependencies. ~150 lines."
        },
        {
          "label": "Add playwright-stealth library",
          "description": "Adds `tf-playwright-stealth` (active fork of playwright-stealth) on top of the above. Patches dozens of fingerprint vectors (WebGL, plugins, codecs, iframe.contentWindow, etc). Heavier but battle-tested. +1 dependency."
        },
        {
          "label": "Custom + per-host rate limiter",
          "description": "Custom evasion (option 1) PLUS a token-bucket limiter so we never exceed ~1 req / 3-5s to Brave, even under burst load. Best if you call Brave from multiple concurrent requests."
        }
      ]
    },
    {
      "question": "Should the evasion apply to all providers or just Brave?",
      "header": "Scope",
      "options": [
        {
          "label": "Brave only for now (Recommended)",
          "description": "Keep DuckDuckGo as-is (it currently works) and only add evasion to brave.py. Easier to review, lower risk of breaking DDG."
        },
        {
          "label": "Refactor into shared helpers",
          "description": "Move UA rotation, headers, init_script, and retry into reusable utilities under browser/ or providers/_humanize.py so both providers (and future ones) benefit."
        }
      ]
    }
  ]
}
```

**Output:**

```
User has answered your questions: "How aggressive should the anti-bot evasion be? This shapes scope and dependencies."="Custom + retry only (Recommended)", "Should the evasion apply to all providers or just Brave?"="Brave only for now (Recommended)". You can now continue with the user's answers in mind.
```

---

## Assistant (Build · Claude Opus 4.7 · 49.4s)

_Thinking:_

I'm outlining the implementation approach with a focus on custom retry logic and Brave-specific settings, starting with configuration parameters for retry attempts, backoff timing, and request intervals.

Now I'm setting up humanization helpers local to the Brave module—building a persona system that combines user agents across different browsers and operating systems with matching viewport sizes, locales, and headers, plus a function to randomly select a coherent persona for each request.

I'm also planning a stealth initialization script that masks common webdriver detection vectors like navigator properties, spoofs the Chrome object for Chromium browsers, and mocks WebGL details to appear more human-like.

For the search flow itself, I'll update the Brave provider to cycle through retry attempts by picking a fresh persona each time, applying the stealth script, adding human-like delays before navigation, handling 429 responses with exponential backoff, and then simulating natural browsing behavior like scrolling before extracting results.

After exhausting retries on 429 errors, I'll raise a ProviderBlockedError to signal the block to the caller.

For testing, I need to verify the persona picker returns consistent user agent and client hints pairs, and mock the browser context and page navigation to simulate both blocked and successful responses.

Now I'm looking at the BrowserManager's context creation signature—it currently accepts locale and viewport as keyword arguments, but I need to pass user agent, extra headers, and timezone per request. I could either extend the existing method to accept these overrides or have Brave create contexts directly from the underlying browser instance, though the first approach keeps things cleaner and maintains better encapsulation.

Since the user wants Brave-only changes and extending the signature with optional parameters won't affect DuckDuckGo's behavior, I'll go with option A and add those optional overrides to the manager's new_context method.

My implementation plan covers updates to the browser manager to accept optional user agent, timezone, and headers; changes to the Brave provider with persona pooling and the retry loop; config additions for Brave-specific retry settings; environment documentation; and new tests for persona consistency and retry behavior.

For the user agent pool, I'm selecting recent ones from late 2025 and early 2026 across Chrome, Firefox, and Edge on Windows, macOS, and Linux.

Now I'm designing the persona structure to bundle user agent, viewport dimensions, locale, timezone, and HTTP headers like Accept-Language and Sec-CH-UA. I'm also planning a stealth injection script that hides webdriver detection, sets up navigator properties like languages and plugins, and mocks the chrome object to avoid detection.

Writing the stealth script...

For the retry mechanism, I'll only retry on ProviderBlockedError (the 429 case) and skip retrying timeouts or unavailable errors. The backoff strategy uses exponential growth with jitter to space out retry attempts.

Computing backoff logic...

Before each search, I should add some human-like behavior—a small random delay before navigation, mouse movements after the page loads, a brief scroll, and another pause before reading content. These should be subtle enough not to significantly slow things down.

For testing, I need to verify the persona picker returns valid personas, that user agent and client hints are properly paired, backoff values increase with jitter, and the retry flow works end-to-end. Since each retry attempt should use a fresh browser context with its own cookies and fingerprint, the retry loop wraps around the context creation.

Let me start implementing this now.

Plan confirmed: custom evasion + retry, Brave-only. Let me track this work and implement.

**Tool: todowrite**

**Input:**

```json
{
  "todos": [
    {
      "content": "Add Brave retry/backoff settings to config.py and .env.example",
      "status": "in_progress",
      "priority": "high"
    },
    {
      "content": "Extend BrowserManager.new_context to accept per-request UA/timezone/headers overrides",
      "status": "pending",
      "priority": "high"
    },
    {
      "content": "Rewrite BraveSearchProvider with persona rotation, stealth init script, jitter, and 429 retry",
      "status": "pending",
      "priority": "high"
    },
    {
      "content": "Add tests for persona picker, backoff calc, and retry loop",
      "status": "pending",
      "priority": "medium"
    },
    {
      "content": "Run linter and full test suite to verify",
      "status": "pending",
      "priority": "high"
    }
  ]
}
```

**Output:**

```
[
  {
    "content": "Add Brave retry/backoff settings to config.py and .env.example",
    "status": "in_progress",
    "priority": "high"
  },
  {
    "content": "Extend BrowserManager.new_context to accept per-request UA/timezone/headers overrides",
    "status": "pending",
    "priority": "high"
  },
  {
    "content": "Rewrite BraveSearchProvider with persona rotation, stealth init script, jitter, and 429 retry",
    "status": "pending",
    "priority": "high"
  },
  {
    "content": "Add tests for persona picker, backoff calc, and retry loop",
    "status": "pending",
    "priority": "medium"
  },
  {
    "content": "Run linter and full test suite to verify",
    "status": "pending",
    "priority": "high"
  }
]
```

---

## Assistant (Build · Claude Opus 4.7 · 5.2s)

Let me also check the existing tests and tooling so the implementation fits the project's conventions:

**Tool: read**

**Input:**

```json
{
  "filePath": "/home/mauro/ws/dev/AI/websearch_api/tests/conftest.py"
}
```

**Output:**

```
<path>/home/mauro/ws/dev/AI/websearch_api/tests/conftest.py</path>
<type>file</type>
<content>
1: """Shared pytest fixtures.
2:
3: Notes
4: -----
5: * The FastAPI app's ``lifespan`` boots Playwright. For unit tests we don't
6:   want a real browser, so :func:`client` overrides
7:   :func:`websearch_api.api.dependencies.get_browser_manager` to return a stub
8:   that satisfies ``BrowserManager``'s public surface.
9: * Provider stubs are injected via ``app.dependency_overrides`` so tests can
10:   assert exactly what the route receives without monkeypatching imports.
11: """
12:
13: from __future__ import annotations
14:
15: from collections.abc import Iterator
16: from pathlib import Path
17:
18: import pytest
19: from fastapi.testclient import TestClient
20:
21: from websearch_api.api.dependencies import (
22:     get_brave,
23:     get_browser_manager,
24:     get_duckduckgo,
25:     get_page_extractor,
26: )
27: from websearch_api.config import Settings, get_settings
28: from websearch_api.main import create_app
29:
30: FIXTURES_DIR = Path(__file__).parent / "fixtures"
31:
32:
33: # --------------------------------------------------------------------------- #
34: # Static HTML fixtures                                                        #
35: # --------------------------------------------------------------------------- #
36: @pytest.fixture
37: def ddg_results_html() -> str:
38:     return (FIXTURES_DIR / "duckduckgo_results.html").read_text(encoding="utf-8")
39:
40:
41: @pytest.fixture
42: def ddg_empty_html() -> str:
43:     return (FIXTURES_DIR / "duckduckgo_empty.html").read_text(encoding="utf-8")
44:
45:
46: # --------------------------------------------------------------------------- #
47: # Settings + browser stubs                                                    #
48: # --------------------------------------------------------------------------- #
49: @pytest.fixture
50: def settings() -> Settings:
51:     """Fresh ``Settings`` instance with deterministic defaults for tests."""
52:     get_settings.cache_clear()
53:     s = Settings(
54:         log_level="WARNING",
55:         default_max_results=5,
56:         max_results_hard_cap=10,
57:         request_timeout_ms=5_000,
58:     )
59:     return s
60:
61:
62: class _StubBrowserManager:
63:     """Stand-in for :class:`BrowserManager` used by API tests.
64:
65:     The provider stubs we inject never actually touch this object, so we only
66:     need to satisfy the public surface the dependency-checker inspects.
67:     """
68:
69:     is_ready: bool = True
70:
71:     async def start(self) -> None:  # pragma: no cover - never called in unit tests
72:         return None
73:
74:     async def stop(self) -> None:  # pragma: no cover
75:         return None
76:
77:
78: # --------------------------------------------------------------------------- #
79: # FastAPI test client                                                         #
80: # --------------------------------------------------------------------------- #
81: @pytest.fixture
82: def client(settings: Settings) -> Iterator[TestClient]:
83:     """A ``TestClient`` whose browser + providers are stubbed by default.
84:
85:     The stub is pre-installed on ``app.state`` so the lifespan does NOT launch
86:     a real Chromium - keeping the unit-test suite fast and dependency-free.
87:     """
88:     app = create_app(settings=settings)
89:     app.state.browser_manager = _StubBrowserManager()
90:
91:     app.dependency_overrides[get_browser_manager] = lambda: _StubBrowserManager()
92:     # We override the settings dependency too so the routes see the same object
93:     # the test created (rather than the lru_cache singleton).
94:     app.dependency_overrides[get_settings] = lambda: settings
95:
96:     with TestClient(app) as c:
97:         yield c
98:
99:     app.dependency_overrides.clear()
100:
101:
102: @pytest.fixture
103: def override_provider(client: TestClient):
104:     """Helper that swaps a provider dependency for a test double.
105:
106:     Usage::
107:
108:         def test_foo(client, override_provider):
109:             override_provider(get_duckduckgo, FakeDDG())
110:             ...
111:     """
112:
113:     def _override(dep, replacement):
114:         client.app.dependency_overrides[dep] = lambda: replacement
115:
116:     return _override
117:
118:
119: @pytest.fixture
120: def brave_dep_key():
121:     return get_brave
122:
123:
124: @pytest.fixture
125: def duckduckgo_dep_key():
126:     return get_duckduckgo
127:
128:
129: @pytest.fixture
130: def extractor_dep_key():
131:     return get_page_extractor

(End of file - total 131 lines)
</content>
```

---

## Assistant (Build · Claude Opus 4.7 · 8.1s)

**Tool: read**

**Input:**

```json
{
  "filePath": "/home/mauro/ws/dev/AI/websearch_api/pyproject.toml"
}
```

**Output:**

```
<path>/home/mauro/ws/dev/AI/websearch_api/pyproject.toml</path>
<type>file</type>
<content>
1: [project]
2: name = "websearch-api"
3: version = "0.1.0"
4: description = "A Tavily-like web search service exposed through a FastAPI HTTP API, powered by Playwright."
5: readme = "README.md"
6: requires-python = ">=3.12"
7: license = { text = "MIT" }
8: authors = [{ name = "websearch-api contributors" }]
9: keywords = ["search", "playwright", "fastapi", "scraping", "tavily", "extract", "crawler"]
10: classifiers = [
11:     "Development Status :: 3 - Alpha",
12:     "Framework :: FastAPI",
13:     "Intended Audience :: Developers",
14:     "License :: OSI Approved :: MIT License",
15:     "Programming Language :: Python :: 3",
16:     "Topic :: Internet :: WWW/HTTP :: Indexing/Search",
17: ]
18:
19: dependencies = [
20:     "fastapi>=0.115.0",
21:     "uvicorn[standard]>=0.32.0",
22:     "pydantic>=2.9.0",
23:     "pydantic-settings>=2.6.0",
24:     "playwright>=1.48.0",
25:     "beautifulsoup4>=4.12.3",
26:     "lxml>=5.3.0",
27:     "httpx>=0.27.0",
28:     "readability-lxml>=0.8.1",
29:     "markdownify>=0.13.1",
30: ]
31:
32: [project.optional-dependencies]
33: dev = [
34:     "pytest>=8.3.0",
35:     "pytest-asyncio>=0.24.0",
36:     "pytest-cov>=5.0.0",
37:     "pytest-mock>=3.14.0",
38:     "ruff>=0.7.0",
39: ]
40:
41: [project.scripts]
42: websearch-api = "websearch_api.__main__:main"
43:
44: [build-system]
45: requires = ["hatchling"]
46: build-backend = "hatchling.build"
47:
48: [tool.hatch.build.targets.wheel]
49: packages = ["src/websearch_api"]
50:
51: [tool.uv]
52: package = true
53:
54: [tool.pytest.ini_options]
55: minversion = "8.0"
56: addopts = [
57:     "-ra",
58:     "--strict-markers",
59:     "--strict-config",
60:     "-m", "not integration",
61: ]
62: testpaths = ["tests"]
63: asyncio_mode = "auto"
64: markers = [
65:     "integration: marks tests that hit real external services (deselected by default; run with -m integration)",
66:     "slow: marks slow-running tests",
67: ]
68:
69: [tool.ruff]
70: line-length = 100
71: target-version = "py312"
72:
73: [tool.ruff.lint]
74: select = [
75:     "E",   # pycodestyle errors
76:     "W",   # pycodestyle warnings
77:     "F",   # pyflakes
78:     "I",   # isort
79:     "B",   # flake8-bugbear
80:     "UP",  # pyupgrade
81:     "SIM", # flake8-simplify
82:     "RUF", # ruff-specific
83: ]
84: ignore = ["E501"]  # handled by formatter
85:
86: [tool.ruff.lint.per-file-ignores]
87: "tests/*" = ["B011"]

(End of file - total 87 lines)
</content>
```

---

## Assistant (Build · Claude Opus 4.7 · 4.0s)

**Tool: bash**

**Input:**

```json
{
  "command": "ls tests/fixtures/ 2>/dev/null || echo \"no fixtures dir\"",
  "description": "Check fixtures directory"
}
```

**Output:**

```
article.html
brave_results.html
duckduckgo_empty.html
duckduckgo_results.html

```

---

## Assistant (Build · Claude Opus 4.7 · 12.3s)

Good - I have everything I need. Now let me implement.

**Step 1: extend `config.py` with retry settings:**

**Tool: edit**

**Input:**

```json
{
  "filePath": "/home/mauro/ws/dev/AI/websearch_api/src/websearch_api/config.py",
  "oldString": "    # --- Browser ---\n    browser_headless: bool = True\n    request_timeout_ms: int = Field(default=20_000, ge=1_000, le=120_000)\n    user_agent: str = (\n        \"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 \"\n        \"(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36\"\n    )\n\n    # --- Search defaults ---\n    default_max_results: int = Field(default=10, ge=1, le=100)\n    max_results_hard_cap: int = Field(default=50, ge=1, le=200)",
  "newString": "    # --- Browser ---\n    browser_headless: bool = True\n    request_timeout_ms: int = Field(default=20_000, ge=1_000, le=120_000)\n    user_agent: str = (\n        \"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 \"\n        \"(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36\"\n    )\n\n    # --- Search defaults ---\n    default_max_results: int = Field(default=10, ge=1, le=100)\n    max_results_hard_cap: int = Field(default=50, ge=1, le=200)\n\n    # --- Brave anti-bot / retry ---\n    # Total attempts (including the first) before giving up on a 429 / bot-gate.\n    brave_retry_attempts: int = Field(default=3, ge=1, le=10)\n    # Exponential backoff: delay = min(base * 2**attempt, max) + 0-30% jitter.\n    brave_retry_backoff_base_ms: int = Field(default=1_500, ge=0, le=60_000)\n    brave_retry_backoff_max_ms: int = Field(default=8_000, ge=0, le=120_000)\n    # Random pre-navigation pause so requests don't arrive on the same wall-clock\n    # tick. Drawn uniformly from [min, max]; set both to 0 to disable.\n    brave_prenav_jitter_min_ms: int = Field(default=200, ge=0, le=10_000)\n    brave_prenav_jitter_max_ms: int = Field(default=1_200, ge=0, le=10_000)"
}
```

**Output:**

```
Edit applied successfully.
```

---

## Assistant (Build · Claude Opus 4.7 · 9.6s)

Now add a validator to keep min ≤ max for jitter, and update `.env.example`:

**Tool: edit**

**Input:**

```json
{
  "filePath": "/home/mauro/ws/dev/AI/websearch_api/src/websearch_api/config.py",
  "oldString": "    @field_validator(\"max_results_hard_cap\")\n    @classmethod\n    def _hard_cap_gte_default(cls, value: int, info) -> int:\n        default = info.data.get(\"default_max_results\", 10)\n        if value < default:\n            raise ValueError(\n                f\"max_results_hard_cap must be >= default_max_results (got {value} < {default})\"\n            )\n        return value",
  "newString": "    @field_validator(\"max_results_hard_cap\")\n    @classmethod\n    def _hard_cap_gte_default(cls, value: int, info) -> int:\n        default = info.data.get(\"default_max_results\", 10)\n        if value < default:\n            raise ValueError(\n                f\"max_results_hard_cap must be >= default_max_results (got {value} < {default})\"\n            )\n        return value\n\n    @field_validator(\"brave_retry_backoff_max_ms\")\n    @classmethod\n    def _backoff_max_gte_base(cls, value: int, info) -> int:\n        base = info.data.get(\"brave_retry_backoff_base_ms\", 0)\n        if value < base:\n            raise ValueError(\n                f\"brave_retry_backoff_max_ms must be >= brave_retry_backoff_base_ms \"\n                f\"(got {value} < {base})\"\n            )\n        return value\n\n    @field_validator(\"brave_prenav_jitter_max_ms\")\n    @classmethod\n    def _jitter_max_gte_min(cls, value: int, info) -> int:\n        lo = info.data.get(\"brave_prenav_jitter_min_ms\", 0)\n        if value < lo:\n            raise ValueError(\n                f\"brave_prenav_jitter_max_ms must be >= brave_prenav_jitter_min_ms \"\n                f\"(got {value} < {lo})\"\n            )\n        return value"
}
```

**Output:**

```
Edit applied successfully.
```

---

## Assistant (Build · Claude Opus 4.7 · 7.7s)

**Tool: edit**

**Input:**

```json
{
  "filePath": "/home/mauro/ws/dev/AI/websearch_api/.env.example",
  "oldString": "# --- Search defaults ---\nWEBSEARCH_DEFAULT_MAX_RESULTS=10\nWEBSEARCH_MAX_RESULTS_HARD_CAP=50",
  "newString": "# --- Search defaults ---\nWEBSEARCH_DEFAULT_MAX_RESULTS=10\nWEBSEARCH_MAX_RESULTS_HARD_CAP=50\n\n# --- Brave anti-bot / retry ---\n# Total attempts (including the first) before surfacing a 429 / bot-gate.\nWEBSEARCH_BRAVE_RETRY_ATTEMPTS=3\n# Exponential backoff window between retries (ms). 0-30% jitter is added.\nWEBSEARCH_BRAVE_RETRY_BACKOFF_BASE_MS=1500\nWEBSEARCH_BRAVE_RETRY_BACKOFF_MAX_MS=8000\n# Random pre-navigation pause to avoid synchronized request bursts.\n# Set both to 0 to disable jitter entirely.\nWEBSEARCH_BRAVE_PRENAV_JITTER_MIN_MS=200\nWEBSEARCH_BRAVE_PRENAV_JITTER_MAX_MS=1200"
}
```

**Output:**

```
Edit applied successfully.
```

---

## Assistant (Build · Claude Opus 4.7 · 6.4s)

**Step 2: extend `BrowserManager.new_context` with per-request overrides.**

**Tool: todowrite**

**Input:**

```json
{
  "todos": [
    {
      "content": "Add Brave retry/backoff settings to config.py and .env.example",
      "status": "completed",
      "priority": "high"
    },
    {
      "content": "Extend BrowserManager.new_context to accept per-request UA/timezone/headers overrides",
      "status": "in_progress",
      "priority": "high"
    },
    {
      "content": "Rewrite BraveSearchProvider with persona rotation, stealth init script, jitter, and 429 retry",
      "status": "pending",
      "priority": "high"
    },
    {
      "content": "Add tests for persona picker, backoff calc, and retry loop",
      "status": "pending",
      "priority": "medium"
    },
    {
      "content": "Run linter and full test suite to verify",
      "status": "pending",
      "priority": "high"
    }
  ]
}
```

**Output:**

```
[
  {
    "content": "Add Brave retry/backoff settings to config.py and .env.example",
    "status": "completed",
    "priority": "high"
  },
  {
    "content": "Extend BrowserManager.new_context to accept per-request UA/timezone/headers overrides",
    "status": "in_progress",
    "priority": "high"
  },
  {
    "content": "Rewrite BraveSearchProvider with persona rotation, stealth init script, jitter, and 429 retry",
    "status": "pending",
    "priority": "high"
  },
  {
    "content": "Add tests for persona picker, backoff calc, and retry loop",
    "status": "pending",
    "priority": "medium"
  },
  {
    "content": "Run linter and full test suite to verify",
    "status": "pending",
    "priority": "high"
  }
]
```

---

## Assistant (Build · Claude Opus 4.7 · 15.4s)

**Tool: edit**

**Input:**

```json
{
  "filePath": "/home/mauro/ws/dev/AI/websearch_api/src/websearch_api/browser/manager.py",
  "oldString": "    @asynccontextmanager\n    async def new_context(\n        self,\n        *,\n        locale: str = \"en-US\",\n        viewport: tuple[int, int] = (1366, 768),\n    ) -> AsyncIterator[BrowserContext]:\n        \"\"\"Yield a fresh isolated browser context, then close it.\n\n        Usage::\n\n            async with browser_manager.new_context() as ctx:\n                page = await ctx.new_page()\n                await page.goto(...)\n        \"\"\"\n        if self._browser is None:\n            raise RuntimeError(\"BrowserManager.start() must be called before new_context()\")\n\n        context = await self._browser.new_context(\n            user_agent=self._settings.user_agent,\n            viewport={\"width\": viewport[0], \"height\": viewport[1]},\n            locale=locale,\n            ignore_https_errors=True,\n        )\n        # Reasonable default; individual goto/wait calls can still override.\n        context.set_default_timeout(self._settings.request_timeout_ms)\n        try:\n            yield context\n        finally:\n            try:\n                await context.close()\n            except Exception:  # pragma: no cover\n                logger.debug(\"error closing context\", exc_info=True)",
  "newString": "    @asynccontextmanager\n    async def new_context(\n        self,\n        *,\n        locale: str = \"en-US\",\n        viewport: tuple[int, int] = (1366, 768),\n        user_agent: str | None = None,\n        timezone_id: str | None = None,\n        extra_http_headers: dict[str, str] | None = None,\n    ) -> AsyncIterator[BrowserContext]:\n        \"\"\"Yield a fresh isolated browser context, then close it.\n\n        Parameters\n        ----------\n        locale, viewport\n            Common defaults; pass-through to Playwright.\n        user_agent\n            Per-call override. ``None`` falls back to ``settings.user_agent``.\n            Providers use this to rotate identities and reduce fingerprinting.\n        timezone_id\n            IANA timezone (e.g. ``\"Europe/Lisbon\"``). When set, Playwright will\n            align ``Intl`` / ``Date`` APIs so the context is internally\n            consistent with the rotated locale.\n        extra_http_headers\n            Additional HTTP headers attached to every request (e.g.\n            ``Accept-Language``, ``Sec-CH-UA-*``, ``Referer``).\n\n        Usage::\n\n            async with browser_manager.new_context() as ctx:\n                page = await ctx.new_page()\n                await page.goto(...)\n        \"\"\"\n        if self._browser is None:\n            raise RuntimeError(\"BrowserManager.start() must be called before new_context()\")\n\n        kwargs: dict[str, object] = {\n            \"user_agent\": user_agent or self._settings.user_agent,\n            \"viewport\": {\"width\": viewport[0], \"height\": viewport[1]},\n            \"locale\": locale,\n            \"ignore_https_errors\": True,\n        }\n        if timezone_id:\n            kwargs[\"timezone_id\"] = timezone_id\n        if extra_http_headers:\n            kwargs[\"extra_http_headers\"] = extra_http_headers\n\n        context = await self._browser.new_context(**kwargs)\n        # Reasonable default; individual goto/wait calls can still override.\n        context.set_default_timeout(self._settings.request_timeout_ms)\n        try:\n            yield context\n        finally:\n            try:\n                await context.close()\n            except Exception:  # pragma: no cover\n                logger.debug(\"error closing context\", exc_info=True)"
}
```

**Output:**

```
Edit applied successfully.
```

---

## Assistant (Build · Claude Opus 4.7 · 6.1s)

**Step 3: rewrite `BraveSearchProvider` with persona rotation, stealth, jitter, and retry.**

**Tool: todowrite**

**Input:**

```json
{
  "todos": [
    {
      "content": "Add Brave retry/backoff settings to config.py and .env.example",
      "status": "completed",
      "priority": "high"
    },
    {
      "content": "Extend BrowserManager.new_context to accept per-request UA/timezone/headers overrides",
      "status": "completed",
      "priority": "high"
    },
    {
      "content": "Rewrite BraveSearchProvider with persona rotation, stealth init script, jitter, and 429 retry",
      "status": "in_progress",
      "priority": "high"
    },
    {
      "content": "Add tests for persona picker, backoff calc, and retry loop",
      "status": "pending",
      "priority": "medium"
    },
    {
      "content": "Run linter and full test suite to verify",
      "status": "pending",
      "priority": "high"
    }
  ]
}
```

**Output:**

```
[
  {
    "content": "Add Brave retry/backoff settings to config.py and .env.example",
    "status": "completed",
    "priority": "high"
  },
  {
    "content": "Extend BrowserManager.new_context to accept per-request UA/timezone/headers overrides",
    "status": "completed",
    "priority": "high"
  },
  {
    "content": "Rewrite BraveSearchProvider with persona rotation, stealth init script, jitter, and 429 retry",
    "status": "in_progress",
    "priority": "high"
  },
  {
    "content": "Add tests for persona picker, backoff calc, and retry loop",
    "status": "pending",
    "priority": "medium"
  },
  {
    "content": "Run linter and full test suite to verify",
    "status": "pending",
    "priority": "high"
  }
]
```

---

## Assistant (Build · Claude Opus 4.7 · 81.9s)

**Tool: write**

**Input:**

```json
{
  "filePath": "/home/mauro/ws/dev/AI/websearch_api/src/websearch_api/providers/brave.py",
  "content": "\"\"\"Brave Search provider.\n\nBrave Search (``search.brave.com``) ships a server-rendered HTML SERP that is\nfriendly to ``Playwright``-driven scraping: the result cards are present in\nthe initial HTML, no captcha gate, no SPA hydration required.\n\nLayout (as of 2025-2026)::\n\n    <div class=\"snippet\" data-type=\"web\">\n      <div class=\"result-wrapper\">\n        <div class=\"result-content\">\n          <a href=\"https://target/url\">\n            <cite class=\"snippet-url\">target.url</cite>\n            <div class=\"title search-snippet-title\">Page Title</div>\n          </a>\n          <div class=\"generic-snippet\">\n            <div class=\"content\">snippet body...</div>\n          </div>\n        </div>\n      </div>\n    </div>\n\nIf Brave ever changes its DOM only :meth:`parse_html` needs to be updated.\n\nAnti-bot strategy\n-----------------\nBrave aggressively rate-limits requests that look like automation. To stay\nunder the radar we:\n\n* Rotate among a small pool of **personas** (a coherent bundle of User-Agent,\n  viewport, locale, timezone, and HTTP headers / client hints).\n* Inject a tiny **stealth init script** that masks the most obvious Playwright\n  giveaways (``navigator.webdriver``, empty ``plugins`` array, missing\n  ``window.chrome``, ``Notification`` permissions mismatch).\n* Add a small **random pre-navigation delay** so concurrent calls don't all\n  hit Brave on the same wall-clock tick.\n* Perform light **human-like activity** on the page (mouse move, micro scroll)\n  before reading content.\n* On HTTP ``429`` (or detected bot gate) we **retry with exponential backoff\n  and jitter**, picking a fresh persona each attempt to avoid feedback loops.\n\nEvery knob (attempt count, backoff window, jitter) is configurable via\n``websearch_api.config.Settings``.\n\"\"\"\n\nfrom __future__ import annotations\n\nimport asyncio\nimport contextlib\nimport logging\nimport random\nfrom dataclasses import dataclass\nfrom typing import ClassVar\nfrom urllib.parse import quote_plus\n\nfrom bs4 import BeautifulSoup\nfrom playwright.async_api import Error as PlaywrightError\nfrom playwright.async_api import Page\nfrom playwright.async_api import TimeoutError as PlaywrightTimeoutError\nfrom pydantic import AnyHttpUrl, ValidationError\n\nfrom websearch_api.exceptions import (\n    ProviderBlockedError,\n    ProviderTimeoutError,\n    ProviderUnavailableError,\n)\nfrom websearch_api.models import SearchResult\nfrom websearch_api.providers.base import SearchProvider\n\nlogger = logging.getLogger(__name__)\n\n\n# --------------------------------------------------------------------------- #\n# Persona pool                                                                #\n# --------------------------------------------------------------------------- #\n@dataclass(frozen=True)\nclass _Persona:\n    \"\"\"A coherent identity bundle used for a single search attempt.\n\n    All fields are correlated: a Windows-Chrome ``user_agent`` ships with the\n    matching ``Sec-CH-UA-Platform`` and ``Accept-Language`` headers, etc. Mixing\n    a macOS UA with a Windows platform header is exactly the kind of\n    inconsistency anti-bot heuristics look for.\n    \"\"\"\n\n    user_agent: str\n    viewport: tuple[int, int]\n    locale: str\n    timezone_id: str\n    accept_language: str\n    sec_ch_ua: str | None  # None for non-Chromium UAs (Firefox)\n    sec_ch_ua_platform: str | None\n    sec_ch_ua_mobile: str = '\"?0\"'\n\n    @property\n    def extra_http_headers(self) -> dict[str, str]:\n        headers: dict[str, str] = {\n            \"Accept\": (\n                \"text/html,application/xhtml+xml,application/xml;q=0.9,\"\n                \"image/avif,image/webp,*/*;q=0.8\"\n            ),\n            \"Accept-Language\": self.accept_language,\n            \"Accept-Encoding\": \"gzip, deflate, br, zstd\",\n            \"Upgrade-Insecure-Requests\": \"1\",\n            \"DNT\": \"1\",\n            \"Sec-Fetch-Dest\": \"document\",\n            \"Sec-Fetch-Mode\": \"navigate\",\n            \"Sec-Fetch-Site\": \"none\",\n            \"Sec-Fetch-User\": \"?1\",\n        }\n        if self.sec_ch_ua:\n            headers[\"Sec-CH-UA\"] = self.sec_ch_ua\n            headers[\"Sec-CH-UA-Mobile\"] = self.sec_ch_ua_mobile\n            if self.sec_ch_ua_platform:\n                headers[\"Sec-CH-UA-Platform\"] = self.sec_ch_ua_platform\n        return headers\n\n\n# Curated late-2025 / early-2026 desktop browser fingerprints. Each tuple is\n# internally consistent (UA matches CH-UA, platform, common viewport).\n_PERSONAS: tuple[_Persona, ...] = (\n    # --- Chrome 131 on Windows 11 ---\n    _Persona(\n        user_agent=(\n            \"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 \"\n            \"(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36\"\n        ),\n        viewport=(1920, 1080),\n        locale=\"en-US\",\n        timezone_id=\"America/New_York\",\n        accept_language=\"en-US,en;q=0.9\",\n        sec_ch_ua='\"Google Chrome\";v=\"131\", \"Chromium\";v=\"131\", \"Not_A Brand\";v=\"24\"',\n        sec_ch_ua_platform='\"Windows\"',\n    ),\n    _Persona(\n        user_agent=(\n            \"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 \"\n            \"(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36\"\n        ),\n        viewport=(1536, 864),\n        locale=\"en-GB\",\n        timezone_id=\"Europe/London\",\n        accept_language=\"en-GB,en;q=0.9\",\n        sec_ch_ua='\"Google Chrome\";v=\"131\", \"Chromium\";v=\"131\", \"Not_A Brand\";v=\"24\"',\n        sec_ch_ua_platform='\"Windows\"',\n    ),\n    # --- Chrome 130 on macOS ---\n    _Persona(\n        user_agent=(\n            \"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 \"\n            \"(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36\"\n        ),\n        viewport=(1440, 900),\n        locale=\"en-US\",\n        timezone_id=\"America/Los_Angeles\",\n        accept_language=\"en-US,en;q=0.9\",\n        sec_ch_ua='\"Google Chrome\";v=\"130\", \"Chromium\";v=\"130\", \"Not_A Brand\";v=\"24\"',\n        sec_ch_ua_platform='\"macOS\"',\n    ),\n    _Persona(\n        user_agent=(\n            \"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 \"\n            \"(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36\"\n        ),\n        viewport=(1680, 1050),\n        locale=\"en-US\",\n        timezone_id=\"America/Chicago\",\n        accept_language=\"en-US,en;q=0.8\",\n        sec_ch_ua='\"Google Chrome\";v=\"131\", \"Chromium\";v=\"131\", \"Not_A Brand\";v=\"24\"',\n        sec_ch_ua_platform='\"macOS\"',\n    ),\n    # --- Edge 131 on Windows 11 ---\n    _Persona(\n        user_agent=(\n            \"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 \"\n            \"(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0\"\n        ),\n        viewport=(1920, 1080),\n        locale=\"en-US\",\n        timezone_id=\"America/Denver\",\n        accept_language=\"en-US,en;q=0.9\",\n        sec_ch_ua='\"Microsoft Edge\";v=\"131\", \"Chromium\";v=\"131\", \"Not_A Brand\";v=\"24\"',\n        sec_ch_ua_platform='\"Windows\"',\n    ),\n    # --- Chrome 131 on Linux ---\n    _Persona(\n        user_agent=(\n            \"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 \"\n            \"(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36\"\n        ),\n        viewport=(1920, 1080),\n        locale=\"en-US\",\n        timezone_id=\"Europe/Berlin\",\n        accept_language=\"en-US,en;q=0.9,de;q=0.8\",\n        sec_ch_ua='\"Google Chrome\";v=\"131\", \"Chromium\";v=\"131\", \"Not_A Brand\";v=\"24\"',\n        sec_ch_ua_platform='\"Linux\"',\n    ),\n    # --- Firefox 133 on Windows ---\n    _Persona(\n        user_agent=(\n            \"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) \"\n            \"Gecko/20100101 Firefox/133.0\"\n        ),\n        viewport=(1366, 768),\n        locale=\"en-US\",\n        timezone_id=\"America/New_York\",\n        accept_language=\"en-US,en;q=0.5\",\n        sec_ch_ua=None,  # Firefox doesn't send client hints\n        sec_ch_ua_platform=None,\n    ),\n    # --- Firefox 133 on macOS ---\n    _Persona(\n        user_agent=(\n            \"Mozilla/5.0 (Macintosh; Intel Mac OS X 14.6; rv:133.0) \"\n            \"Gecko/20100101 Firefox/133.0\"\n        ),\n        viewport=(1440, 900),\n        locale=\"en-US\",\n        timezone_id=\"America/Los_Angeles\",\n        accept_language=\"en-US,en;q=0.5\",\n        sec_ch_ua=None,\n        sec_ch_ua_platform=None,\n    ),\n)\n\n\n# --------------------------------------------------------------------------- #\n# Stealth init script                                                         #\n# --------------------------------------------------------------------------- #\n# Runs in every new document before any site JS. Goal is to neutralise the\n# most common cheap detectors. We do **not** aim for full puppeteer-extra\n# parity here; for that, install ``tf-playwright-stealth``.\ndef _build_stealth_script(persona: _Persona) -> str:\n    # Build a JS array literal of locale strings, e.g. ['en-US', 'en'].\n    primary = persona.locale\n    base = primary.split(\"-\", 1)[0]\n    langs = [primary] if primary == base else [primary, base]\n    js_langs = \"[\" + \",\".join(f\"'{lang}'\" for lang in langs) + \"]\"\n\n    return f\"\"\"\n    // 1. Hide the webdriver flag.\n    Object.defineProperty(Navigator.prototype, 'webdriver', {{\n        get: () => undefined,\n        configurable: true,\n    }});\n\n    // 2. Make navigator.languages match the persona locale.\n    Object.defineProperty(Navigator.prototype, 'languages', {{\n        get: () => {js_langs},\n        configurable: true,\n    }});\n\n    // 3. Provide a non-empty plugins array - headless Chromium reports [].\n    Object.defineProperty(Navigator.prototype, 'plugins', {{\n        get: () => {{\n            const fake = [1, 2, 3, 4, 5];\n            fake.item = (i) => fake[i];\n            fake.namedItem = () => null;\n            fake.refresh = () => undefined;\n            return fake;\n        }},\n        configurable: true,\n    }});\n\n    // 4. window.chrome is present in real Chrome but missing in headless.\n    if (!window.chrome) {{\n        window.chrome = {{ runtime: {{}}, csi: () => {{}}, loadTimes: () => {{}} }};\n    }}\n\n    // 5. Permissions API consistency: Notification.permission must match\n    //    permissions.query({{name:'notifications'}}). Detectors check this.\n    const _origQuery = window.navigator.permissions && window.navigator.permissions.query;\n    if (_origQuery) {{\n        window.navigator.permissions.query = (parameters) => (\n            parameters && parameters.name === 'notifications'\n                ? Promise.resolve({{ state: Notification.permission }})\n                : _origQuery.call(window.navigator.permissions, parameters)\n        );\n    }}\n\n    // 6. WebGL vendor/renderer commonly leak \"SwiftShader\" / \"Google Inc.\"\n    //    in headless. Spoof to look like a real GPU. (Light touch - we don't\n    //    spoof every GL parameter, just the two most-fingerprinted ones.)\n    try {{\n        const _getParam = WebGLRenderingContext.prototype.getParameter;\n        WebGLRenderingContext.prototype.getParameter = function (parameter) {{\n            // UNMASKED_VENDOR_WEBGL = 37445, UNMASKED_RENDERER_WEBGL = 37446\n            if (parameter === 37445) return 'Intel Inc.';\n            if (parameter === 37446) return 'Intel Iris OpenGL Engine';\n            return _getParam.apply(this, [parameter]);\n        }};\n    }} catch (e) {{ /* WebGL not available - ignore */ }}\n    \"\"\"\n\n\n# --------------------------------------------------------------------------- #\n# Persona / backoff helpers (module-level so they're easy to unit test)       #\n# --------------------------------------------------------------------------- #\ndef _pick_persona(rng: random.Random | None = None) -> _Persona:\n    \"\"\"Choose a random persona. ``rng`` injectable for deterministic tests.\"\"\"\n    return (rng or random).choice(_PERSONAS)\n\n\ndef _compute_backoff_ms(\n    attempt: int,\n    *,\n    base_ms: int,\n    max_ms: int,\n    rng: random.Random | None = None,\n) -> int:\n    \"\"\"Exponential backoff with 0-30% jitter, capped at ``max_ms``.\n\n    ``attempt`` is 0-indexed (first retry passes 0).\n    \"\"\"\n    rand = rng or random\n    exp_delay = min(base_ms * (2**attempt), max_ms)\n    jitter = rand.uniform(0, exp_delay * 0.3)\n    return int(exp_delay + jitter)\n\n\n# --------------------------------------------------------------------------- #\n# Provider                                                                    #\n# --------------------------------------------------------------------------- #\nclass BraveSearchProvider(SearchProvider):\n    \"\"\"Search backed by ``https://search.brave.com/search``.\"\"\"\n\n    name: ClassVar[str] = \"brave\"\n    SEARCH_URL: ClassVar[str] = \"https://search.brave.com/search\"\n    HOMEPAGE_URL: ClassVar[str] = \"https://search.brave.com/\"\n\n    async def search(self, query: str, *, max_results: int) -> list[SearchResult]:\n        limit = self._clamp(max_results)\n        attempts = self._settings.brave_retry_attempts\n        logger.info(\n            \"brave.search\", extra={\"query\": query, \"limit\": limit, \"max_attempts\": attempts}\n        )\n\n        last_exc: ProviderBlockedError | None = None\n        for attempt in range(attempts):\n            persona = _pick_persona()\n            try:\n                return await self._search_once(query, limit=limit, persona=persona)\n            except ProviderBlockedError as exc:\n                last_exc = exc\n                if attempt + 1 >= attempts:\n                    break\n                delay_ms = _compute_backoff_ms(\n                    attempt,\n                    base_ms=self._settings.brave_retry_backoff_base_ms,\n                    max_ms=self._settings.brave_retry_backoff_max_ms,\n                )\n                logger.warning(\n                    \"brave blocked (%s); retrying in %dms (attempt %d/%d)\",\n                    exc,\n                    delay_ms,\n                    attempt + 2,\n                    attempts,\n                )\n                await asyncio.sleep(delay_ms / 1000)\n\n        # Exhausted all retries.\n        assert last_exc is not None  # for type-checker\n        raise last_exc\n\n    # ------------------------------------------------------------------ #\n    # one search attempt                                                 #\n    # ------------------------------------------------------------------ #\n    async def _search_once(\n        self, query: str, *, limit: int, persona: _Persona\n    ) -> list[SearchResult]:\n        url = f\"{self.SEARCH_URL}?q={quote_plus(query)}\"\n\n        # Pre-navigation jitter: avoid synchronised bursts when callers fan out.\n        await self._sleep_prenav_jitter()\n\n        async with self._browser.new_context(\n            user_agent=persona.user_agent,\n            viewport=persona.viewport,\n            locale=persona.locale,\n            timezone_id=persona.timezone_id,\n            extra_http_headers=persona.extra_http_headers,\n        ) as ctx:\n            await ctx.add_init_script(script=_build_stealth_script(persona))\n\n            page = await ctx.new_page()\n            try:\n                response = await page.goto(url, wait_until=\"domcontentloaded\")\n            except PlaywrightTimeoutError as exc:\n                raise ProviderTimeoutError(\n                    f\"brave did not load within {self._settings.request_timeout_ms}ms\"\n                ) from exc\n            except PlaywrightError as exc:\n                raise ProviderUnavailableError(f\"brave navigation failed: {exc}\") from exc\n\n            if response is None:\n                raise ProviderUnavailableError(\"brave returned no response\")\n            if response.status == 429:\n                raise ProviderBlockedError(\"brave rate-limited the request (429)\")\n            if response.status >= 400:\n                raise ProviderUnavailableError(f\"brave returned HTTP {response.status}\")\n\n            # Give the Svelte app a brief moment to finish hydration; the SERP\n            # cards are already in the initial HTML, but a small settle helps\n            # when Brave inlines lazy snippets. No results = legitimate empty\n            # response, so we suppress the timeout.\n            with contextlib.suppress(PlaywrightTimeoutError):\n                await page.wait_for_selector('div.snippet[data-type=\"web\"]', timeout=5_000)\n\n            # Tiny human-ish dwell: mouse move + micro scroll + short pause.\n            # Best-effort - any failure here must not break the search.\n            with contextlib.suppress(PlaywrightError, PlaywrightTimeoutError):\n                await self._humanize(page)\n\n            html = await page.content()\n\n        if _looks_like_block(html):\n            raise ProviderBlockedError(\"brave returned an anti-bot challenge\")\n\n        return self.parse_html(html, max_results=limit, source=self.name)\n\n    # ------------------------------------------------------------------ #\n    # human-ish behaviour helpers                                        #\n    # ------------------------------------------------------------------ #\n    async def _sleep_prenav_jitter(self) -> None:\n        lo = self._settings.brave_prenav_jitter_min_ms\n        hi = self._settings.brave_prenav_jitter_max_ms\n        if hi <= 0:\n            return\n        delay_ms = random.randint(lo, hi) if hi > lo else lo\n        if delay_ms > 0:\n            await asyncio.sleep(delay_ms / 1000)\n\n    @staticmethod\n    async def _humanize(page: Page) -> None:\n        \"\"\"Perform a couple of cheap, low-noise user-like gestures.\"\"\"\n        # Random cursor position somewhere in the visible area.\n        x = random.randint(120, 900)\n        y = random.randint(120, 600)\n        await page.mouse.move(x, y, steps=random.randint(5, 15))\n        # Micro scroll (under one viewport).\n        await page.mouse.wheel(0, random.randint(100, 350))\n        # Short dwell before we read content.\n        await asyncio.sleep(random.uniform(0.15, 0.45))\n\n    # ------------------------------------------------------------------ #\n    # Pure parser - unit-testable without a browser                      #\n    # ------------------------------------------------------------------ #\n    @staticmethod\n    def parse_html(html: str, *, max_results: int, source: str = \"brave\") -> list[SearchResult]:\n        \"\"\"Parse a Brave SERP into structured ``SearchResult`` rows.\"\"\"\n        soup = BeautifulSoup(html, \"lxml\")\n        results: list[SearchResult] = []\n\n        for block in soup.select('div.snippet[data-type=\"web\"]'):\n            link = block.select_one(\"a[href^=http]\")\n            if link is None:\n                continue\n            href = link.get(\"href\") or \"\"\n\n            title_el = block.select_one(\n                \"div.title.search-snippet-title, div.title, .search-snippet-title\"\n            )\n            if title_el is None:\n                # Fall back to the anchor's site-name label if no dedicated title.\n                title_el = block.select_one(\".site-name-content .text-ellipsis\")\n            title = title_el.get_text(\" \", strip=True) if title_el else \"\"\n\n            snippet_el = block.select_one(\"div.generic-snippet .content, div.snippet-content\")\n            snippet = snippet_el.get_text(\" \", strip=True) if snippet_el else None\n\n            cite_el = block.select_one(\"cite.snippet-url, cite\")\n            metadata: dict[str, str] = {}\n            if cite_el:\n                metadata[\"displayed_url\"] = cite_el.get_text(\" \", strip=True)\n\n            try:\n                results.append(\n                    SearchResult(\n                        title=title or href,\n                        url=AnyHttpUrl(href),\n                        snippet=snippet,\n                        rank=len(results) + 1,\n                        source=source,\n                        metadata=metadata,\n                    )\n                )\n            except ValidationError:\n                logger.debug(\"skipping malformed brave result href=%r\", href)\n                continue\n\n            if len(results) >= max_results:\n                break\n\n        return results\n\n\ndef _looks_like_block(html: str) -> bool:\n    \"\"\"Heuristic: detect Brave's bot/captcha gate.\"\"\"\n    needles = (\n        \"Are you human?\",\n        \"captcha-bypass\",\n        \"challenge-platform\",\n    )\n    return any(needle in html for needle in needles)\n"
}
```

**Output:**

```
Wrote file successfully.
```

---

## Assistant (Build · Claude Opus 4.7 · 7.3s)

**Step 4: tests.** First let me look at existing tests for conventions:

**Tool: read**

**Input:**

```json
{
  "filePath": "/home/mauro/ws/dev/AI/websearch_api/tests/test_providers_duckduckgo.py",
  "limit": 50
}
```

**Output:**

```
<path>/home/mauro/ws/dev/AI/websearch_api/tests/test_providers_duckduckgo.py</path>
<type>file</type>
<content>
1: """Unit tests for the DuckDuckGo provider's pure parser."""
2:
3: from __future__ import annotations
4:
5: from websearch_api.providers.duckduckgo import DuckDuckGoProvider, _clean_ddg_url
6:
7:
8: def test_parse_html_extracts_organic_results(ddg_results_html: str) -> None:
9:     results = DuckDuckGoProvider.parse_html(ddg_results_html, max_results=10)
10:
11:     # Three organic results in the fixture; the ad and the malformed block are skipped.
12:     assert len(results) == 3
13:     titles = [r.title for r in results]
14:     assert titles == [
15:         "Python downloads page",
16:         "Python 3 docs",
17:         "Real Python",
18:     ]
19:
20:     first = results[0]
21:     assert str(first.url) == "https://python.org/downloads"
22:     assert "Python Programming Language" in (first.snippet or "")
23:     assert first.rank == 1
24:     assert first.source == "duckduckgo"
25:     assert first.metadata.get("displayed_url") == "python.org/downloads"
26:
27:
28: def test_parse_html_honours_max_results(ddg_results_html: str) -> None:
29:     results = DuckDuckGoProvider.parse_html(ddg_results_html, max_results=2)
30:     assert len(results) == 2
31:     assert [r.rank for r in results] == [1, 2]
32:
33:
34: def test_parse_html_returns_empty_for_no_results(ddg_empty_html: str) -> None:
35:     assert DuckDuckGoProvider.parse_html(ddg_empty_html, max_results=10) == []
36:
37:
38: def test_clean_ddg_url_unwraps_redirect() -> None:
39:     href = "//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fa%2Fb&rut=abc"
40:     assert _clean_ddg_url(href) == "https://example.com/a/b"
41:
42:
43: def test_clean_ddg_url_passes_through_direct_links() -> None:
44:     assert _clean_ddg_url("https://example.com/x") == "https://example.com/x"
45:
46:
47: def test_clean_ddg_url_rejects_unusable_input() -> None:
48:     assert _clean_ddg_url("") is None
49:     assert _clean_ddg_url("javascript:void(0)") is None
50:     assert _clean_ddg_url("/internal/path") is None

(Showing lines 1-50 of 55. Use offset=51 to continue.)
</content>
```

---

## Assistant (Build · Claude Opus 4.7 · 6.0s)

**Tool: todowrite**

**Input:**

```json
{
  "todos": [
    {
      "content": "Add Brave retry/backoff settings to config.py and .env.example",
      "status": "completed",
      "priority": "high"
    },
    {
      "content": "Extend BrowserManager.new_context to accept per-request UA/timezone/headers overrides",
      "status": "completed",
      "priority": "high"
    },
    {
      "content": "Rewrite BraveSearchProvider with persona rotation, stealth init script, jitter, and 429 retry",
      "status": "completed",
      "priority": "high"
    },
    {
      "content": "Add tests for persona picker, backoff calc, and retry loop",
      "status": "in_progress",
      "priority": "medium"
    },
    {
      "content": "Run linter and full test suite to verify",
      "status": "pending",
      "priority": "high"
    }
  ]
}
```

**Output:**

```
[
  {
    "content": "Add Brave retry/backoff settings to config.py and .env.example",
    "status": "completed",
    "priority": "high"
  },
  {
    "content": "Extend BrowserManager.new_context to accept per-request UA/timezone/headers overrides",
    "status": "completed",
    "priority": "high"
  },
  {
    "content": "Rewrite BraveSearchProvider with persona rotation, stealth init script, jitter, and 429 retry",
    "status": "completed",
    "priority": "high"
  },
  {
    "content": "Add tests for persona picker, backoff calc, and retry loop",
    "status": "in_progress",
    "priority": "medium"
  },
  {
    "content": "Run linter and full test suite to verify",
    "status": "pending",
    "priority": "high"
  }
]
```

---

## Assistant (Build · Claude Opus 4.7 · 52.3s)

Now I'll extend the brave tests with persona, backoff, stealth-script, and retry coverage:

**Tool: edit**

**Input:**

```json
{
  "filePath": "/home/mauro/ws/dev/AI/websearch_api/tests/test_providers_brave.py",
  "oldString": "\"\"\"Unit tests for the Brave Search provider's pure parser.\"\"\"\n\nfrom __future__ import annotations\n\nfrom pathlib import Path\n\nimport pytest\n\nfrom websearch_api.providers.brave import BraveSearchProvider, _looks_like_block\n\nFIXTURES_DIR = Path(__file__).parent / \"fixtures\"\n\n\n@pytest.fixture\ndef brave_results_html() -> str:\n    return (FIXTURES_DIR / \"brave_results.html\").read_text(encoding=\"utf-8\")\n\n\ndef test_parse_html_extracts_web_results(brave_results_html: str) -> None:\n    results = BraveSearchProvider.parse_html(brave_results_html, max_results=10)\n\n    # 3 organic web results in the fixture. The news card and the malformed\n    # web card without an anchor are both skipped.\n    assert len(results) == 3\n    titles = [r.title for r in results]\n    assert titles == [\n        \"FastAPI\",\n        \"Using FastAPI to Build Python Web APIs - Real Python\",\n        \"tiangolo/fastapi - GitHub\",\n    ]\n\n    first = results[0]\n    assert str(first.url) == \"https://fastapi.tiangolo.com/\"\n    assert first.snippet is not None\n    assert \"FastAPI is a modern, fast\" in first.snippet\n    assert first.rank == 1\n    assert first.source == \"brave\"\n    assert first.metadata.get(\"displayed_url\") == \"fastapi.tiangolo.com\"\n\n\ndef test_parse_html_honours_max_results(brave_results_html: str) -> None:\n    results = BraveSearchProvider.parse_html(brave_results_html, max_results=2)\n    assert len(results) == 2\n    assert [r.rank for r in results] == [1, 2]\n\n\ndef test_parse_html_returns_empty_for_no_results() -> None:\n    assert BraveSearchProvider.parse_html(\"<html></html>\", max_results=10) == []\n\n\ndef test_looks_like_block_detects_captcha() -> None:\n    assert _looks_like_block(\"<html>Are you human? please verify...</html>\") is True\n    assert _looks_like_block(\"<html>normal content</html>\") is False\n\n\ndef test_results_are_sequentially_ranked(brave_results_html: str) -> None:\n    results = BraveSearchProvider.parse_html(brave_results_html, max_results=10)\n    assert [r.rank for r in results] == list(range(1, len(results) + 1))",
  "newString": "\"\"\"Unit tests for the Brave Search provider's pure parser and humanisation layer.\"\"\"\n\nfrom __future__ import annotations\n\nimport random\nfrom pathlib import Path\nfrom typing import Any\nfrom unittest.mock import AsyncMock, MagicMock\n\nimport pytest\n\nfrom websearch_api.config import Settings\nfrom websearch_api.exceptions import (\n    ProviderBlockedError,\n    ProviderUnavailableError,\n)\nfrom websearch_api.providers.brave import (\n    _PERSONAS,\n    BraveSearchProvider,\n    _build_stealth_script,\n    _compute_backoff_ms,\n    _looks_like_block,\n    _pick_persona,\n)\n\nFIXTURES_DIR = Path(__file__).parent / \"fixtures\"\n\n\n@pytest.fixture\ndef brave_results_html() -> str:\n    return (FIXTURES_DIR / \"brave_results.html\").read_text(encoding=\"utf-8\")\n\n\n# --------------------------------------------------------------------------- #\n# Pure parser                                                                 #\n# --------------------------------------------------------------------------- #\ndef test_parse_html_extracts_web_results(brave_results_html: str) -> None:\n    results = BraveSearchProvider.parse_html(brave_results_html, max_results=10)\n\n    # 3 organic web results in the fixture. The news card and the malformed\n    # web card without an anchor are both skipped.\n    assert len(results) == 3\n    titles = [r.title for r in results]\n    assert titles == [\n        \"FastAPI\",\n        \"Using FastAPI to Build Python Web APIs - Real Python\",\n        \"tiangolo/fastapi - GitHub\",\n    ]\n\n    first = results[0]\n    assert str(first.url) == \"https://fastapi.tiangolo.com/\"\n    assert first.snippet is not None\n    assert \"FastAPI is a modern, fast\" in first.snippet\n    assert first.rank == 1\n    assert first.source == \"brave\"\n    assert first.metadata.get(\"displayed_url\") == \"fastapi.tiangolo.com\"\n\n\ndef test_parse_html_honours_max_results(brave_results_html: str) -> None:\n    results = BraveSearchProvider.parse_html(brave_results_html, max_results=2)\n    assert len(results) == 2\n    assert [r.rank for r in results] == [1, 2]\n\n\ndef test_parse_html_returns_empty_for_no_results() -> None:\n    assert BraveSearchProvider.parse_html(\"<html></html>\", max_results=10) == []\n\n\ndef test_looks_like_block_detects_captcha() -> None:\n    assert _looks_like_block(\"<html>Are you human? please verify...</html>\") is True\n    assert _looks_like_block(\"<html>normal content</html>\") is False\n\n\ndef test_results_are_sequentially_ranked(brave_results_html: str) -> None:\n    results = BraveSearchProvider.parse_html(brave_results_html, max_results=10)\n    assert [r.rank for r in results] == list(range(1, len(results) + 1))\n\n\n# --------------------------------------------------------------------------- #\n# Persona pool                                                                #\n# --------------------------------------------------------------------------- #\ndef test_persona_pool_is_non_empty_and_unique() -> None:\n    assert len(_PERSONAS) >= 4\n    # Every persona must have a UA, and we want at least some UA diversity.\n    uas = [p.user_agent for p in _PERSONAS]\n    assert all(uas), \"every persona must define a non-empty user_agent\"\n    assert len(set(uas)) >= 3, \"expected at least 3 distinct user-agent strings\"\n\n\ndef test_persona_chrome_ua_carries_consistent_client_hints() -> None:\n    \"\"\"Chrome/Edge UAs must ship Sec-CH-UA. Firefox UAs must not.\"\"\"\n    for persona in _PERSONAS:\n        is_chromium = \"Chrome/\" in persona.user_agent or \"Edg/\" in persona.user_agent\n        is_firefox = \"Firefox/\" in persona.user_agent\n\n        if is_chromium:\n            assert persona.sec_ch_ua, f\"chromium persona missing Sec-CH-UA: {persona.user_agent}\"\n            headers = persona.extra_http_headers\n            assert \"Sec-CH-UA\" in headers\n            assert \"Sec-CH-UA-Platform\" in headers\n            assert \"Sec-CH-UA-Mobile\" in headers\n        elif is_firefox:\n            assert persona.sec_ch_ua is None, \"firefox does not send Sec-CH-UA\"\n            assert \"Sec-CH-UA\" not in persona.extra_http_headers\n\n\ndef test_persona_headers_always_include_accept_language() -> None:\n    for persona in _PERSONAS:\n        headers = persona.extra_http_headers\n        assert headers[\"Accept-Language\"]\n        assert headers[\"Accept\"].startswith(\"text/html\")\n        assert headers[\"Sec-Fetch-Mode\"] == \"navigate\"\n\n\ndef test_pick_persona_uses_provided_rng_for_determinism() -> None:\n    rng = random.Random(42)\n    first = _pick_persona(rng)\n    # Reseeding the same rng must reproduce the same choice.\n    second = _pick_persona(random.Random(42))\n    assert first is second\n    assert first in _PERSONAS\n\n\n# --------------------------------------------------------------------------- #\n# Stealth init script                                                         #\n# --------------------------------------------------------------------------- #\ndef test_stealth_script_targets_all_known_fingerprint_vectors() -> None:\n    persona = _PERSONAS[0]\n    script = _build_stealth_script(persona)\n\n    # Each tweak we promise in the module docstring must appear.\n    assert \"webdriver\" in script\n    assert \"languages\" in script\n    assert \"plugins\" in script\n    assert \"window.chrome\" in script\n    assert \"Notification.permission\" in script\n    assert \"WebGLRenderingContext\" in script\n\n    # The locale array must reflect the persona's locale.\n    primary = persona.locale\n    base = primary.split(\"-\", 1)[0]\n    assert f\"'{primary}'\" in script\n    if primary != base:\n        assert f\"'{base}'\" in script\n\n\ndef test_stealth_script_handles_locale_without_region() -> None:\n    \"\"\"Edge case: a persona with a bare ``'en'`` locale produces a single-item list.\"\"\"\n    persona = _PERSONAS[0]\n    # Build a synthetic persona using the same dataclass-shape via copy.\n    bare = type(persona)(\n        user_agent=persona.user_agent,\n        viewport=persona.viewport,\n        locale=\"en\",\n        timezone_id=persona.timezone_id,\n        accept_language=\"en;q=0.9\",\n        sec_ch_ua=persona.sec_ch_ua,\n        sec_ch_ua_platform=persona.sec_ch_ua_platform,\n    )\n    script = _build_stealth_script(bare)\n    assert \"['en']\" in script\n\n\n# --------------------------------------------------------------------------- #\n# Backoff                                                                     #\n# --------------------------------------------------------------------------- #\ndef test_backoff_grows_exponentially_and_is_capped() -> None:\n    rng = random.Random(0)\n    delays = [\n        _compute_backoff_ms(i, base_ms=1_000, max_ms=8_000, rng=rng) for i in range(6)\n    ]\n    # Expected exponent: 1000, 2000, 4000, 8000, 8000, 8000 (capped).\n    # Jitter adds 0-30%, so each value must sit in [exp, exp*1.3].\n    expected_min = [1000, 2000, 4000, 8000, 8000, 8000]\n    for got, lo in zip(delays, expected_min, strict=True):\n        assert lo <= got <= int(lo * 1.3) + 1\n\n\ndef test_backoff_zero_base_returns_zero() -> None:\n    rng = random.Random(0)\n    assert _compute_backoff_ms(0, base_ms=0, max_ms=8_000, rng=rng) == 0\n    assert _compute_backoff_ms(3, base_ms=0, max_ms=8_000, rng=rng) == 0\n\n\n# --------------------------------------------------------------------------- #\n# Retry loop                                                                  #\n# --------------------------------------------------------------------------- #\ndef _make_provider(\n    settings: Settings | None = None,\n    *,\n    page_factory,\n) -> BraveSearchProvider:\n    \"\"\"Build a provider whose browser is fully mocked.\n\n    ``page_factory`` is a zero-arg callable returning the next mocked Page.\n    We return a new page per ``new_context()`` so retries get a fresh stub.\n    \"\"\"\n    s = settings or Settings(\n        log_level=\"WARNING\",\n        request_timeout_ms=5_000,\n        brave_retry_attempts=3,\n        brave_retry_backoff_base_ms=0,  # fast tests\n        brave_retry_backoff_max_ms=0,\n        brave_prenav_jitter_min_ms=0,\n        brave_prenav_jitter_max_ms=0,\n    )\n\n    browser = MagicMock()\n\n    class _CtxCM:\n        async def __aenter__(self) -> Any:\n            ctx = MagicMock()\n            ctx.add_init_script = AsyncMock()\n            ctx.new_page = AsyncMock(return_value=page_factory())\n            return ctx\n\n        async def __aexit__(self, *exc_info: object) -> None:\n            return None\n\n    browser.new_context = MagicMock(return_value=_CtxCM())\n\n    return BraveSearchProvider(browser=browser, settings=s)\n\n\ndef _stub_page(*, status: int, html: str = \"<html></html>\") -> MagicMock:\n    page = MagicMock()\n    response = MagicMock()\n    response.status = status\n    page.goto = AsyncMock(return_value=response)\n    page.wait_for_selector = AsyncMock()\n    page.content = AsyncMock(return_value=html)\n    page.mouse = MagicMock()\n    page.mouse.move = AsyncMock()\n    page.mouse.wheel = AsyncMock()\n    return page\n\n\nasync def test_search_retries_on_429_then_succeeds(brave_results_html: str) -> None:\n    \"\"\"First attempt 429, second attempt 200 with valid HTML -> success.\"\"\"\n    pages = iter(\n        [\n            _stub_page(status=429),\n            _stub_page(status=200, html=brave_results_html),\n        ]\n    )\n    provider = _make_provider(page_factory=lambda: next(pages))\n\n    results = await provider.search(\"fastapi\", max_results=3)\n\n    assert len(results) == 3\n    # Two new_context calls means two attempts.\n    assert provider._browser.new_context.call_count == 2\n\n\nasync def test_search_raises_after_exhausting_retries() -> None:\n    \"\"\"All attempts hit 429 -> ProviderBlockedError surfaces to the caller.\"\"\"\n    provider = _make_provider(page_factory=lambda: _stub_page(status=429))\n\n    with pytest.raises(ProviderBlockedError):\n        await provider.search(\"anything\", max_results=5)\n\n    assert provider._browser.new_context.call_count == 3  # attempts=3\n\n\nasync def test_search_does_not_retry_on_non_429_http_error() -> None:\n    \"\"\"A 503 is a different failure mode; surfacing it lets callers decide.\"\"\"\n    provider = _make_provider(page_factory=lambda: _stub_page(status=503))\n\n    with pytest.raises(ProviderUnavailableError):\n        await provider.search(\"anything\", max_results=5)\n\n    # No retries: ProviderUnavailableError exits the loop immediately.\n    assert provider._browser.new_context.call_count == 1\n\n\nasync def test_search_retries_when_html_looks_like_bot_gate() -> None:\n    \"\"\"A 200 OK body containing the captcha needle counts as blocked.\"\"\"\n    pages = iter(\n        [\n            _stub_page(status=200, html=\"<html>Are you human?</html>\"),\n            _stub_page(status=200, html=\"<html></html>\"),  # empty SERP, but unblocked\n        ]\n    )\n    provider = _make_provider(page_factory=lambda: next(pages))\n\n    results = await provider.search(\"anything\", max_results=5)\n\n    assert results == []\n    assert provider._browser.new_context.call_count == 2"
}
```

**Output:**

```
Edit applied successfully.
```

---

## Assistant (Build · Claude Opus 4.7 · 6.8s)

**Step 5: lint + test.**

**Tool: todowrite**

**Input:**

```json
{
  "todos": [
    {
      "content": "Add Brave retry/backoff settings to config.py and .env.example",
      "status": "completed",
      "priority": "high"
    },
    {
      "content": "Extend BrowserManager.new_context to accept per-request UA/timezone/headers overrides",
      "status": "completed",
      "priority": "high"
    },
    {
      "content": "Rewrite BraveSearchProvider with persona rotation, stealth init script, jitter, and 429 retry",
      "status": "completed",
      "priority": "high"
    },
    {
      "content": "Add tests for persona picker, backoff calc, and retry loop",
      "status": "completed",
      "priority": "medium"
    },
    {
      "content": "Run linter and full test suite to verify",
      "status": "in_progress",
      "priority": "high"
    }
  ]
}
```

**Output:**

```
[
  {
    "content": "Add Brave retry/backoff settings to config.py and .env.example",
    "status": "completed",
    "priority": "high"
  },
  {
    "content": "Extend BrowserManager.new_context to accept per-request UA/timezone/headers overrides",
    "status": "completed",
    "priority": "high"
  },
  {
    "content": "Rewrite BraveSearchProvider with persona rotation, stealth init script, jitter, and 429 retry",
    "status": "completed",
    "priority": "high"
  },
  {
    "content": "Add tests for persona picker, backoff calc, and retry loop",
    "status": "completed",
    "priority": "medium"
  },
  {
    "content": "Run linter and full test suite to verify",
    "status": "in_progress",
    "priority": "high"
  }
]
```

---

## Assistant (Build · Claude Opus 4.7 · 3.8s)

**Tool: bash**

**Input:**

```json
{
  "command": ".venv/bin/ruff check src tests",
  "description": "Lint the code"
}
```

**Output:**

```
All checks passed!

```

---

## Assistant (Build · Claude Opus 4.7 · 4.2s)

**Tool: bash**

**Input:**

```json
{
  "command": ".venv/bin/ruff format --check src tests",
  "description": "Check formatting"
}
```

**Output:**

```
Would reformat: src/websearch_api/providers/brave.py
Would reformat: tests/test_providers_brave.py
2 files would be reformatted, 23 files already formatted

```

---

## Assistant (Build · Claude Opus 4.7 · 3.5s)

**Tool: bash**

**Input:**

```json
{
  "command": ".venv/bin/ruff format src tests",
  "description": "Auto-format"
}
```

**Output:**

```
2 files reformatted, 23 files left unchanged

```

---

## Assistant (Build · Claude Opus 4.7 · 6.0s)

**Tool: bash**

**Input:**

```json
{
  "command": ".venv/bin/pytest -q 2>&1 | tail -80",
  "description": "Run full test suite"
}
```

**Output:**

```
.............................................................            [100%]
61 passed in 1.36s

```

---

## Assistant (Build · Claude Opus 4.7 · 6.5s)

All 61 tests pass. Let me also confirm the lint output is still clean after formatting and verify the new tests are exercising the right code paths:

**Tool: bash**

**Input:**

```json
{
  "command": ".venv/bin/ruff check src tests && .venv/bin/pytest tests/test_providers_brave.py tests/test_config.py -v 2>&1 | tail -40",
  "description": "Final lint + targeted tests"
}
```

**Output:**

```
All checks passed!
============================= test session starts ==============================
platform linux -- Python 3.14.3, pytest-9.0.3, pluggy-1.6.0 -- /home/mauro/ws/dev/AI/websearch_api/.venv/bin/python3
cachedir: .pytest_cache
rootdir: /home/mauro/ws/dev/AI/websearch_api
configfile: pyproject.toml
plugins: asyncio-1.3.0, mock-3.15.1, cov-7.1.0, anyio-4.13.0
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 21 items

tests/test_providers_brave.py::test_parse_html_extracts_web_results PASSED [  4%]
tests/test_providers_brave.py::test_parse_html_honours_max_results PASSED [  9%]
tests/test_providers_brave.py::test_parse_html_returns_empty_for_no_results PASSED [ 14%]
tests/test_providers_brave.py::test_looks_like_block_detects_captcha PASSED [ 19%]
tests/test_providers_brave.py::test_results_are_sequentially_ranked PASSED [ 23%]
tests/test_providers_brave.py::test_persona_pool_is_non_empty_and_unique PASSED [ 28%]
tests/test_providers_brave.py::test_persona_chrome_ua_carries_consistent_client_hints PASSED [ 33%]
tests/test_providers_brave.py::test_persona_headers_always_include_accept_language PASSED [ 38%]
tests/test_providers_brave.py::test_pick_persona_uses_provided_rng_for_determinism PASSED [ 42%]
tests/test_providers_brave.py::test_stealth_script_targets_all_known_fingerprint_vectors PASSED [ 47%]
tests/test_providers_brave.py::test_stealth_script_handles_locale_without_region PASSED [ 52%]
tests/test_providers_brave.py::test_backoff_grows_exponentially_and_is_capped PASSED [ 57%]
tests/test_providers_brave.py::test_backoff_zero_base_returns_zero PASSED [ 61%]
tests/test_providers_brave.py::test_search_retries_on_429_then_succeeds PASSED [ 66%]
tests/test_providers_brave.py::test_search_raises_after_exhausting_retries PASSED [ 71%]
tests/test_providers_brave.py::test_search_does_not_retry_on_non_429_http_error PASSED [ 76%]
tests/test_providers_brave.py::test_search_retries_when_html_looks_like_bot_gate PASSED [ 80%]
tests/test_config.py::test_defaults_are_sane PASSED                      [ 85%]
tests/test_config.py::test_env_overrides PASSED                          [ 90%]
tests/test_config.py::test_invalid_log_level_rejected PASSED             [ 95%]
tests/test_config.py::test_hard_cap_must_be_ge_default PASSED            [100%]

============================== 21 passed in 1.16s ==============================

```

---

## Assistant (Build · Claude Opus 4.7 · 5.2s)

**Tool: todowrite**

**Input:**

```json
{
  "todos": [
    {
      "content": "Add Brave retry/backoff settings to config.py and .env.example",
      "status": "completed",
      "priority": "high"
    },
    {
      "content": "Extend BrowserManager.new_context to accept per-request UA/timezone/headers overrides",
      "status": "completed",
      "priority": "high"
    },
    {
      "content": "Rewrite BraveSearchProvider with persona rotation, stealth init script, jitter, and 429 retry",
      "status": "completed",
      "priority": "high"
    },
    {
      "content": "Add tests for persona picker, backoff calc, and retry loop",
      "status": "completed",
      "priority": "medium"
    },
    {
      "content": "Run linter and full test suite to verify",
      "status": "completed",
      "priority": "high"
    }
  ]
}
```

**Output:**

```
[
  {
    "content": "Add Brave retry/backoff settings to config.py and .env.example",
    "status": "completed",
    "priority": "high"
  },
  {
    "content": "Extend BrowserManager.new_context to accept per-request UA/timezone/headers overrides",
    "status": "completed",
    "priority": "high"
  },
  {
    "content": "Rewrite BraveSearchProvider with persona rotation, stealth init script, jitter, and 429 retry",
    "status": "completed",
    "priority": "high"
  },
  {
    "content": "Add tests for persona picker, backoff calc, and retry loop",
    "status": "completed",
    "priority": "medium"
  },
  {
    "content": "Run linter and full test suite to verify",
    "status": "completed",
    "priority": "high"
  }
]
```

---

## Assistant (Build · Claude Opus 4.7 · 18.3s)

Done. Summary of what changed:

## What changed

**`src/websearch_api/providers/brave.py`** — full anti-bot rework:

- **8 personas** (Chrome/Edge/Firefox × Win/Mac/Linux) rotated per attempt. Each persona bundles a coherent `(UA, viewport, locale, timezone, Accept-Language, Sec-CH-UA*, ...)` — no Linux UA paired with Windows hints, no missing client-hints on Chrome.
- **Stealth init script** injected into every context. Hides `navigator.webdriver`, fills `navigator.plugins`, adds `window.chrome`, fixes the `Notification.permission` vs `permissions.query` inconsistency, and spoofs WebGL vendor/renderer (the two most-fingerprinted GL params).
- **Pre-navigation jitter** (configurable, default 200–1200ms) so concurrent calls don't fire on the same tick.
- **Human-ish dwell** after load: random mouse move + micro scroll + ~150-450ms pause before reading content. Best-effort, never breaks the search.
- **429-aware retry** with exponential backoff + 0–30% jitter (default: 3 attempts, base 1.5s, cap 8s). A fresh persona is picked per attempt so we don't retry with the same fingerprint that just got blocked. Non-429 errors (timeout, 5xx) are NOT retried — they fail fast.

**`src/websearch_api/browser/manager.py`** — `new_context()` now accepts optional per-call `user_agent`, `timezone_id`, and `extra_http_headers`. Defaults unchanged, so DuckDuckGo is untouched.

**`src/websearch_api/config.py`** + **`.env.example`** — 5 new tunable settings under `WEBSEARCH_BRAVE_*` with cross-field validators (`max ≥ base`, `max ≥ min`).

**`tests/test_providers_brave.py`** — 12 new tests covering: persona pool consistency, Chrome-vs-Firefox header rules, stealth script coverage, locale-without-region edge case, exponential backoff bounds with seeded RNG, and four retry-loop scenarios (`429→200`, `429×N`, `503 no-retry`, `200+captcha→200`).

## Result

- **Lint:** `ruff check` clean, `ruff format` clean.
- **Tests:** 61/61 passing in 1.36s. The retry tests use mocks, so no real network or browser is touched.

## Tuning knobs (in `.env`)

```env
WEBSEARCH_BRAVE_RETRY_ATTEMPTS=3
WEBSEARCH_BRAVE_RETRY_BACKOFF_BASE_MS=1500
WEBSEARCH_BRAVE_RETRY_BACKOFF_MAX_MS=8000
WEBSEARCH_BRAVE_PRENAV_JITTER_MIN_MS=200
WEBSEARCH_BRAVE_PRENAV_JITTER_MAX_MS=1200
```

If you still see 429s under load, the most effective dial is **`BRAVE_PRENAV_JITTER_MAX_MS`** (push it to 3000–5000) — bursting is what triggers Brave's limiter more than fingerprint alone. If that's still not enough, ping me and I'll add the per-host token-bucket limiter (option 3 from earlier).

---
