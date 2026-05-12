# websearch-api

A small **web search + page-extract HTTP service** backed by
Playwright. It accepts a query (or an arbitrary URL), drives a real browser,
and returns structured JSON: search results or cleaned article content with
text + Markdown + links + metadata.

The service exposes two primitives - `/search` and `/extract` - and that's
enough to compose into vertical workflows (LinkedIn discovery, news triage,
RAG ingestion, ...). See [`example.md`](./example.md) for HTTPie recipes.

The codebase is intentionally tiny and easy to extend:

- one abstract `SearchProvider` + two concrete implementations
  (`BraveSearchProvider`, `DuckDuckGoProvider`)
- a `PageExtractor` for arbitrary-URL crawling (single-page
  ``/extract``), with `readability` for boilerplate removal and `markdownify`
  for HTML → Markdown
- single long-lived Chromium instance, fresh isolated context per request
- pure HTML parsers - testable without a browser
- FastAPI app with auto-generated Swagger docs at `/docs`

> **Default provider: Brave Search.** Brave's SERP is server-rendered and
> friendly to automated browsers. DuckDuckGo is still bundled but is
> *best-effort* — its HTML endpoint aggressively challenges headless traffic
> and frequently returns empty results from data-center IPs. See
> [Provider lineup](#provider-lineup) below.

---

## Table of contents

- [Architecture](#architecture)
- [Provider lineup](#provider-lineup)
- [Setup with mise + uv](#setup-with-mise--uv)
- [Running the service](#running-the-service)
- [API reference](#api-reference)
- [Crawling any website: the `/extract` endpoint](#crawling-any-website-the-extract-endpoint)
- [Worked examples](#worked-examples)
- [Configuration reference](#configuration-reference)
- [Development workflow](#development-workflow)
- [Extending: add a new provider](#extending-add-a-new-provider)
- [Troubleshooting](#troubleshooting)

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                            FastAPI app                                   │
│  POST /api/v1/search        ──┐                                          │
│  GET  /api/v1/search        ──┤                                          │
│  POST /api/v1/extract       ──┤                                          │
│  GET  /api/v1/extract       ──┤                                          │
│  GET  /api/v1/health, /providers                                         │
└─────────────────────────────┬─┴───────────────────────────────────────────┘
                              │ depends on
                              ▼
                 ┌──────────────────────────────┐
                 │   SearchProvider (ABC)       │      PageExtractor
                 │   ├── BraveSearchProvider    │   (readability + markdownify
                 │   └── DuckDuckGoProvider     │    over arbitrary URLs)
                 └──────────────┬───────────────┘
                                │ uses
                                ▼
                 ┌──────────────────────────────┐
                 │   BrowserManager (Playwright)│
                 │   - single Chromium process  │
                 │   - fresh context per request│
                 └──────────────────────────────┘
```

Each provider is split into two halves:

| Half          | What it does                                  | Tested how                  |
| ------------- | --------------------------------------------- | --------------------------- |
| `search(...)` | drives Playwright, fetches HTML               | integration test (opt-in)   |
| `parse_html()`| **pure function** that turns HTML → models    | unit tests against fixtures |

This split keeps the test suite fast (no browser required for the default run)
while still letting you verify the live wiring on demand with
`mise run test:integration`.

Layout:

```
src/websearch_api/
├── main.py               # FastAPI app factory + lifespan + exception handlers
├── __main__.py           # `python -m websearch_api` entry point
├── config.py             # pydantic-settings, env-driven configuration
├── logging_config.py     # text + JSON log formatters
├── models.py             # request / response Pydantic models
├── exceptions.py         # domain exceptions translated to HTTP codes
├── browser/manager.py    # Playwright lifecycle (one browser, many contexts)
├── providers/
│   ├── base.py           # SearchProvider abstract base class
│   ├── brave.py          # Brave Search HTML SERP parser + driver (default)
│   └── duckduckgo.py     # DuckDuckGo HTML SERP parser + driver (best-effort)
├── extractors/
│   └── page.py           # PageExtractor: fetch arbitrary URL → text/markdown/links
└── api/
    ├── routes.py         # endpoint definitions
    └── dependencies.py   # FastAPI dependency wiring
tests/
├── conftest.py           # TestClient + provider override helpers
├── fixtures/             # static HTML samples for parser tests
├── test_providers_*.py   # parser unit tests
├── test_extractor.py     # PageExtractor unit tests
├── test_api.py           # HTTP endpoint tests w/ stubbed providers
└── test_config.py        # settings / env-var tests
example.md                # HTTPie recipes for every endpoint + worked examples
```

---

## Provider lineup

| Provider     | `provider` value | Default? | Reliability                 | Notes                                       |
| ------------ | ---------------- | -------- | --------------------------- | ------------------------------------------- |
| Brave Search | `brave`          | **yes**  | High - works headless       | Server-rendered SERP at `search.brave.com`. |
| DuckDuckGo   | `duckduckgo`     | no       | Best-effort - frequently 0  | Their HTML endpoint bot-checks headless traffic from data-center IPs. The provider is kept because (a) it works from many residential networks and (b) the parser stays useful if DDG ever rolls back the gate. |

If `duckduckgo` returns `result_count: 0`, that's not a bug - it's DDG's
anti-bot response coming back as an empty page. Switch `"provider": "brave"`
(or omit the field) for reliable web results.

Need vertical scraping (LinkedIn jobs, GitHub issues, a specific marketplace)?
The right approach is **composition, not new providers**: use `/search` with
the `site:` operator to discover URLs, then `/extract` to pull each page's
content. See the worked LinkedIn example below.

---

## Setup with mise + uv

### Prerequisites

- [`mise`](https://mise.jdx.dev/) - manages Python and `uv` versions for this repo.
  Install once: `curl https://mise.run | sh`.
- A POSIX-y shell.

### Bootstrap

```bash
# 1. Install Python 3.14 and the latest uv (versions pinned in mise.toml).
mise install

# 2. Sync Python deps and install the Playwright browser binary.
#    Defined as a task in mise.toml so it's one command:
mise run install
```

The `install` task runs:

```bash
uv sync --extra dev
uv run playwright install chromium
```

`uv sync` provisions `.venv/` and installs every dependency (including dev
extras) from `pyproject.toml` in a reproducible way. `playwright install` then
downloads the Chromium browser bundle Playwright drives. The Chromium download
is ~150 MB and happens once.

> On Linux you may also need OS-level dependencies for Chromium. If the browser
> fails to start, run:
>
> ```bash
> uv run playwright install-deps chromium
> ```

### Optional: local `.env`

```bash
cp .env.example .env
# edit values as needed (the defaults work out-of-the-box)
```

---

## Running the service

```bash
mise run serve
```

This is equivalent to:

```bash
uv run uvicorn websearch_api.main:app --host 0.0.0.0 --port 8000 --reload
```

On startup you'll see Chromium being launched once. Open
<http://127.0.0.1:8000/docs> for the auto-generated Swagger UI.

Health check:

```bash
curl -s http://127.0.0.1:8000/api/v1/health | jq
```

```json
{ "status": "ok", "version": "0.1.0", "browser_ready": true }
```

---

## API reference

All endpoints return JSON. Errors use a uniform envelope:

```json
{ "error": "provider_timeout", "detail": "brave did not load within 20000ms" }
```

| Method | Path                       | Purpose                                        |
| ------ | -------------------------- | ---------------------------------------------- |
| GET    | `/api/v1/health`           | Liveness probe + browser readiness             |
| GET    | `/api/v1/providers`        | List configured search providers               |
| POST   | `/api/v1/search`           | Generic web search (structured body)           |
| GET    | `/api/v1/search?q=...`     | Generic web search (URL query convenience)     |
| POST   | `/api/v1/extract`          | Crawl a single URL → cleaned text + Markdown   |
| GET    | `/api/v1/extract?url=...`  | Crawl a single URL (URL query convenience)     |

### `POST /api/v1/search`

Request body (the `provider` field is optional - defaults to `brave`):

```json
{
  "query": "fastapi background tasks",
  "max_results": 5,
  "provider": "brave"
}
```

Response (`200 OK`):

```json
{
  "query": "fastapi background tasks",
  "provider": "brave",
  "result_count": 5,
  "elapsed_ms": 1170,
  "fetched_at": "2026-05-11T14:10:20.070369+00:00",
  "results": [
    {
      "title": "Background Tasks - FastAPI",
      "url": "https://fastapi.tiangolo.com/tutorial/background-tasks/",
      "snippet": "You can define background tasks to be run after returning a response...",
      "rank": 1,
      "source": "brave",
      "metadata": { "displayed_url": "fastapi.tiangolo.com \u203a tutorial  \u203a background-tasks" }
    }
  ]
}
```

Status codes:

| Code | When                                                                  |
| ---- | --------------------------------------------------------------------- |
| 200  | Success (including `result_count == 0` - empty SERPs are not errors). |
| 422  | Query is missing, empty, or unknown provider name supplied.           |
| 502  | Provider returned an unexpected response or anti-bot challenge.       |
| 503  | Browser pool not ready (only briefly during startup).                 |
| 504  | Provider did not respond within `WEBSEARCH_REQUEST_TIMEOUT_MS`.       |

---

## Crawling any website: the `/extract` endpoint

`POST /api/v1/extract` takes an arbitrary URL, fetches it with Playwright, runs
the response HTML through `readability-lxml` to strip nav / footer / ads /
scripts, and returns the **main content** as both plain text and Markdown.
Outbound links from the article body and head-tag metadata
(og:* / canonical / favicon / description / language / published_at) are
returned alongside.

### Request

```http
POST /api/v1/extract
Content-Type: application/json
```

```json
{
  "url": "https://fastapi.tiangolo.com/tutorial/background-tasks/",
  "wait_for_selector": null,
  "include_html": false,
  "include_links": true
}
```

| Field               | Type    | Default | Notes                                                              |
| ------------------- | ------- | ------- | ------------------------------------------------------------------ |
| `url`               | string  | -       | **Required.** Absolute `http(s)://` URL.                           |
| `wait_for_selector` | string? | `null`  | CSS selector to wait for before snapshotting (useful for SPAs).    |
| `include_html`      | bool    | `false` | If `true`, include the cleaned main-content HTML in the response.  |
| `include_links`     | bool    | `true`  | If `false`, return an empty `links` array (slightly faster).       |

### Response (`200 OK`)

```json
{
  "url": "https://fastapi.tiangolo.com/tutorial/background-tasks/",
  "final_url": "https://fastapi.tiangolo.com/tutorial/background-tasks/",
  "status_code": 200,
  "elapsed_ms": 743,
  "fetched_at": "2026-05-11T14:32:10.123Z",
  "title": "Background Tasks - FastAPI",
  "description": "FastAPI framework, high performance, easy to learn, ...",
  "author": null,
  "language": "en",
  "site_name": null,
  "published_at": null,
  "text": "Background Tasks You can define background tasks to be run after returning a response. ...",
  "markdown": "# Background Tasks\n\nYou can define background tasks to be run *after* returning a response.\n\n...",
  "html": null,
  "links": [
    {
      "text": "starlette.background",
      "url": "https://www.starlette.dev/background/",
      "rel": null
    }
  ],
  "metadata": {
    "canonical": "https://fastapi.tiangolo.com/tutorial/background-tasks/",
    "og:image": "https://fastapi.tiangolo.com/img/og-image.png",
    "twitter:card": "summary_large_image"
  }
}
```

### Quick recipes

```bash
# 1) Simplest possible call - plain content extraction
curl -sS http://127.0.0.1:8000/api/v1/extract \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com/"}' | jq

# 2) GET variant (handy for one-liners and browser testing)
curl -sS "http://127.0.0.1:8000/api/v1/extract?url=https://example.com/&include_links=false" | jq

# 3) Pull only the markdown body (great for piping into an LLM)
curl -sS http://127.0.0.1:8000/api/v1/extract \
  -H "Content-Type: application/json" \
  -d '{"url":"https://en.wikipedia.org/wiki/Site_reliability_engineering"}' \
  | jq -r .markdown

# 4) JS-heavy SPA - wait for the main content to hydrate
curl -sS http://127.0.0.1:8000/api/v1/extract \
  -H "Content-Type: application/json" \
  -d '{"url":"https://app.example.com/docs/page","wait_for_selector":"article.docs"}' | jq

# 5) Chain it with search: pick the first hit, then extract its content
URL=$(curl -sS "http://127.0.0.1:8000/api/v1/search?q=fastapi+background+tasks&max_results=1" \
        | jq -r '.results[0].url')
curl -sS "http://127.0.0.1:8000/api/v1/extract?url=$URL" | jq '{title, markdown}'
```

### Status codes

| Code | When                                                                  |
| ---- | --------------------------------------------------------------------- |
| 200  | The URL was fetched. Check `status_code` for the upstream HTTP code.  |
| 422  | `url` is missing, malformed, or not an `http(s)://` URL.              |
| 502  | Target site rate-limited the request (`429`) or refused to load.      |
| 503  | Browser pool not ready (only briefly during startup).                 |
| 504  | Target site did not respond within `WEBSEARCH_REQUEST_TIMEOUT_MS`.    |

> The endpoint deliberately treats `4xx`/`5xx` responses from the target site
> as successful extractions and surfaces the upstream code in `status_code` -
> callers usually want to see the 404 page text rather than receive a 502 here.
> Only `429` is escalated to a `502 Bad Gateway` because it indicates a hard
> block rather than a missing page.

---

## Worked examples

Every endpoint is demonstrated with copy-pasteable [HTTPie](https://httpie.io/)
commands in [`example.md`](./example.md). That doc also walks through a
**LinkedIn workflow** built entirely on top of the two generic endpoints
(`/search` + `/extract`) - no dedicated LinkedIn provider:

1. Use `site:linkedin.com/pulse <query>` against `/search` to discover URLs.
2. Pipe each result URL into `/extract` to get the article text + Markdown.

The same composition pattern works for any vertical: GitHub issues, Hacker
News posts, RFC documents, etc.

```bash
# Find a Pulse article on Python performance and pull its Markdown
URL=$(http -b GET :8000/api/v1/search \
        q=="site:linkedin.com/pulse python performance" max_results==1 \
        | jq -r '.results[0].url')
http --ignore-stdin -b POST :8000/api/v1/extract url="$URL" | jq -r .markdown
```

See [`example.md`](./example.md) for the full set of recipes and the table of
which LinkedIn page types work well (Pulse articles, Company pages) versus
those that don't (individual job postings - login wall).

---

## Configuration reference

Every setting is read from environment variables (also from a local `.env`
file). Defaults shipped in [`src/websearch_api/config.py`](src/websearch_api/config.py).

| Variable                          | Default      | Notes                                                            |
| --------------------------------- | ------------ | ---------------------------------------------------------------- |
| `WEBSEARCH_HOST`                  | `0.0.0.0`    | Bind host for uvicorn.                                           |
| `WEBSEARCH_PORT`                  | `8000`       | Bind port for uvicorn.                                           |
| `WEBSEARCH_LOG_LEVEL`             | `INFO`       | One of `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`.          |
| `WEBSEARCH_LOG_FORMAT`            | `text`       | `text` (human) or `json` (machine).                              |
| `WEBSEARCH_BROWSER_HEADLESS`      | `true`       | Set `false` to watch the browser drive (great for selector dev). |
| `WEBSEARCH_REQUEST_TIMEOUT_MS`    | `20000`      | Per-page navigation timeout.                                     |
| `WEBSEARCH_USER_AGENT`            | Chrome-ish   | Override the UA presented to providers.                          |
| `WEBSEARCH_DEFAULT_MAX_RESULTS`   | `10`         | When the request omits `max_results`.                            |
| `WEBSEARCH_MAX_RESULTS_HARD_CAP`  | `50`         | Server-side ceiling, regardless of request.                      |
| `WEBSEARCH_CORS_ORIGINS`          | `*`          | Comma-separated list, or `*` for all.                            |

---

## Development workflow

All common operations are mise tasks - run `mise tasks` to see them all.

```bash
mise run install          # one-shot setup (deps + browser)
mise run serve            # uvicorn with --reload
mise run test             # fast unit + API tests (no network)
mise run test:integration # opt-in tests that hit real Brave / target sites
mise run lint             # ruff check + format check
mise run format           # ruff format .
```

The default `pytest` invocation excludes anything marked `integration` so the
suite runs in a few seconds and never touches the network. Integration tests
(if you add them) should look like:

```python
import pytest

@pytest.mark.integration
async def test_real_brave(...):
    ...
```

---

## Extending: add a new provider

1. Create `src/websearch_api/providers/my_provider.py`:

   ```python
   from typing import ClassVar
   from websearch_api.providers.base import SearchProvider
   from websearch_api.models import SearchResult

   class MyProvider(SearchProvider):
       name: ClassVar[str] = "my_provider"

       async def search(self, query: str, *, max_results: int) -> list[SearchResult]:
           limit = self._clamp(max_results)
           async with self._browser.new_context() as ctx:
               page = await ctx.new_page()
               await page.goto(f"https://example.com/?q={query}")
               html = await page.content()
           return self.parse_html(html, max_results=limit)

       @staticmethod
       def parse_html(html: str, *, max_results: int) -> list[SearchResult]:
           ...  # pure function, unit-testable
   ```

2. Register it in `src/websearch_api/providers/__init__.py`:

   ```python
   PROVIDER_REGISTRY = {
       BraveSearchProvider.name: BraveSearchProvider,
       DuckDuckGoProvider.name: DuckDuckGoProvider,
       MyProvider.name: MyProvider,
   }
   ```

3. Extend the `ProviderName` `Literal` in `src/websearch_api/models.py` so
   FastAPI's request validation accepts the new name.

4. Add a fixture HTML + parser test under `tests/`.

That's it - the `POST /api/v1/search` endpoint will accept
`"provider": "my_provider"` immediately.

---

## Troubleshooting

**"Executable doesn't exist at .../chromium..."**
Run `mise run install` (or `uv run playwright install chromium`) once.

**Chromium errors about missing system libs on Linux**
Run `uv run playwright install-deps chromium`. On Debian/Ubuntu this installs
the necessary `libnss3`, `libatk-bridge2.0-0`, etc.

**`POST /api/v1/search` with `"provider": "duckduckgo"` returns `result_count: 0`**
That's DDG's anti-bot wall returning a friendly-looking error page instead of a
SERP. Use the default `brave` provider, or run the service from a residential
network where DDG is less aggressive. See [Provider lineup](#provider-lineup).

**`/api/v1/extract` returns very little text on a JavaScript-heavy SPA**
`readability` extracts whatever is in the DOM at snapshot time. If the page
hydrates content client-side, pass `wait_for_selector` (e.g. `"article"` or
`"main .content"`) so the extractor waits for the real content before grabbing
the HTML. Adjust `WEBSEARCH_REQUEST_TIMEOUT_MS` if the page is slow to load.

**Want to watch Playwright drive the browser?**
```bash
WEBSEARCH_BROWSER_HEADLESS=false mise run serve
```

**Logs as JSON for log shippers**
```bash
WEBSEARCH_LOG_FORMAT=json mise run serve
```

---

## License

MIT
