# websearch-api - usage examples

Every endpoint, demonstrated with [HTTPie](https://httpie.io/).

All examples assume the server is running locally on `127.0.0.1:8000`. Start it
with `mise run serve` (or `uv run uvicorn websearch_api.main:app --port 8000`),
then run any command below in another terminal.

## Table of contents

- [Prerequisites](#prerequisites)
- [Meta endpoints](#meta-endpoints)
  - [`GET /` - redirect to docs](#get----redirect-to-docs)
  - [`GET /api/v1/health`](#get-apiv1health)
  - [`GET /api/v1/providers`](#get-apiv1providers)
- [Web search](#web-search)
  - [`POST /api/v1/search`](#post-apiv1search)
  - [`GET /api/v1/search`](#get-apiv1search)
- [Crawl / page extract](#crawl--page-extract)
  - [`POST /api/v1/extract`](#post-apiv1extract)
  - [`GET /api/v1/extract`](#get-apiv1extract)
- [Pipelines: search → extract](#pipelines-search--extract)
- [Worked example: LinkedIn workflows](#worked-example-linkedin-workflows)
- [Error responses](#error-responses)

---

## Prerequisites

Install HTTPie if you don't already have it:

```bash
# macOS / Linux
brew install httpie
# or
pipx install httpie
# or via uv
uv tool install httpie
```

Quick sanity check that the server is up:

```bash
http :8000/api/v1/health
```

> **HTTPie cheat sheet for this doc**
>
> - `field=value`            → JSON string body field
> - `field:=value`           → JSON non-string body field (bool / int / object)
> - `param==value`           → URL query parameter
> - `:8000/path`             → shorthand for `http://127.0.0.1:8000/path`
> - `-b`                     → print response body only
> - `--pretty=all`           → keep colors when piping
> - `--ignore-stdin`         → **add this whenever you pipe HTTPie into another
>   command** (`jq`, `python`, `xargs`, …). Without it, HTTPie sees the pipe and
>   refuses to mix stdin with `key=value` body items, failing with `Request
>   body (from stdin, --raw or a file) and request data (key=value) cannot be
>   mixed`. Examples below add the flag where it's needed.

---

## Meta endpoints

### `GET /` - redirect to docs

```bash
http :8000/
```

Returns a `307` redirect to `/docs` (the Swagger UI). Add `--follow` if you
want HTTPie to chase it:

```bash
http --follow :8000/
```

### `GET /api/v1/health`

```bash
http :8000/api/v1/health
```

```json
{
  "status": "ok",
  "version": "0.1.0",
  "browser_ready": true
}
```

`status` is `"degraded"` if the Chromium pool hasn't finished warming up.

### `GET /api/v1/providers`

```bash
http :8000/api/v1/providers
```

```json
{
  "providers": ["brave", "duckduckgo"]
}
```

---

## Web search

### `POST /api/v1/search`

Minimal call (Brave is the default provider):

```bash
http POST :8000/api/v1/search query="fastapi python"
```

With all options:

```bash
http POST :8000/api/v1/search \
  query="fastapi background tasks" \
  max_results:=5 \
  provider="brave"
```

Response (trimmed):

```json
{
  "query": "fastapi python",
  "provider": "brave",
  "result_count": 5,
  "elapsed_ms": 1170,
  "fetched_at": "2026-05-11T14:10:20.070369Z",
  "results": [
    {
      "title": "FastAPI",
      "url": "https://fastapi.tiangolo.com/",
      "snippet": "FastAPI is a modern, fast (high-performance), web framework for building APIs with Python based on standard Python type hints.",
      "rank": 1,
      "source": "brave",
      "metadata": { "displayed_url": "fastapi.tiangolo.com" }
    }
  ]
}
```

Explicit DuckDuckGo (best-effort - frequently returns 0 results from
data-center IPs):

```bash
http POST :8000/api/v1/search query="hello world" provider="duckduckgo"
```

### `GET /api/v1/search`

Convenience GET variant - same response shape, query params instead of a body:

```bash
http GET :8000/api/v1/search q=="site reliability engineering" max_results==3
```

```bash
http GET :8000/api/v1/search q=="machine learning" provider==brave max_results==10
```

---

## Crawl / page extract

### `POST /api/v1/extract`

Fetch an arbitrary URL, run it through the readability pipeline, return cleaned
text + Markdown + links + metadata. Use this to crawl any website.

Minimal call:

```bash
http POST :8000/api/v1/extract url="https://fastapi.tiangolo.com/tutorial/background-tasks/"
```

Response (trimmed):

```json
{
  "url": "https://fastapi.tiangolo.com/tutorial/background-tasks/",
  "final_url": "https://fastapi.tiangolo.com/tutorial/background-tasks/",
  "status_code": 200,
  "elapsed_ms": 743,
  "fetched_at": "2026-05-11T14:32:10.123Z",
  "title": "Background Tasks - FastAPI",
  "description": "FastAPI framework, high performance, easy to learn, fast to code, ready for production",
  "author": null,
  "language": "en",
  "site_name": null,
  "published_at": null,
  "text": "Background Tasks You can define background tasks to be run after returning a response. ...",
  "markdown": "# Background Tasks\n\nYou can define background tasks to be run *after* returning a response.\n\n...",
  "html": null,
  "links": [
    { "text": "starlette.background", "url": "https://www.starlette.dev/background/", "rel": null },
    { "text": "Celery", "url": "https://docs.celeryq.dev/", "rel": null }
  ],
  "metadata": {
    "canonical": "https://fastapi.tiangolo.com/tutorial/background-tasks/",
    "og:image": "https://fastapi.tiangolo.com/img/og-image.png",
    "twitter:card": "summary_large_image"
  }
}
```

#### All options

```bash
http POST :8000/api/v1/extract \
  url="https://en.wikipedia.org/wiki/Site_reliability_engineering" \
  wait_for_selector="#content" \
  include_html:=true \
  include_links:=true
```

| Field               | Type    | Default | Effect                                                        |
| ------------------- | ------- | ------- | ------------------------------------------------------------- |
| `url`               | string  | -       | Required, `http(s)://` only.                                  |
| `wait_for_selector` | string  | `null`  | Wait for this CSS selector before snapshotting (SPAs).        |
| `include_html`      | bool    | `false` | Include cleaned main-content HTML in the response.            |
| `include_links`     | bool    | `true`  | Set `false` to skip link extraction (slightly faster).        |

#### Useful slices with `jq`

Just the markdown (perfect for piping into an LLM):

```bash
http --ignore-stdin -b POST :8000/api/v1/extract \
    url="https://en.wikipedia.org/wiki/Python_(programming_language)" \
  | jq -r .markdown
```

Title + first 5 links only:

```bash
http --ignore-stdin -b POST :8000/api/v1/extract \
    url="https://en.wikipedia.org/wiki/Site_reliability_engineering" \
  | jq '{title, links: (.links[:5])}'
```

### `GET /api/v1/extract`

Same endpoint, query-parameter form. Quote the URL value:

```bash
http GET :8000/api/v1/extract url=="https://example.com/" include_links==false
```

```bash
http GET :8000/api/v1/extract \
  url=="https://fastapi.tiangolo.com/" \
  include_html==true
```

---

## Pipelines: search → extract

A common workflow: search for something, then pull the full content of the top
hit. Bash + `jq` + HTTPie make it a one-liner (note `--ignore-stdin` on the
piped POST):

```bash
# 1. Find the top result for a query
TOP_URL=$(http -b GET :8000/api/v1/search q=="fastapi background tasks" max_results==1 \
            | jq -r '.results[0].url')

# 2. Extract its full content as Markdown
http --ignore-stdin -b POST :8000/api/v1/extract url="$TOP_URL" \
  | jq -r .markdown
```

Or as one chained pipe:

```bash
http -b GET :8000/api/v1/search q=="python type hints" max_results==1 \
  | jq -r '.results[0].url' \
  | xargs -I {} http --ignore-stdin -b POST :8000/api/v1/extract url="{}" \
  | jq '{title, description, text: (.text[:400] + "...")}'
```

---

## Worked example: LinkedIn workflows

The service exposes two primitives - `/search` and `/extract` - and that's
enough to build vertical workflows against most sites. This section walks
through a few useful **LinkedIn** workflows so you can see how the two
endpoints compose. There is no dedicated LinkedIn endpoint; everything is
plain HTTPie calls against the generic API.

### 1. Discover LinkedIn URLs with `site:`

Use Brave's `site:` operator through `/api/v1/search` to find LinkedIn URLs
that match a query:

```bash
http --ignore-stdin -b GET :8000/api/v1/search \
  q=="site:linkedin.com/jobs python backend Berlin" \
  max_results==5
```

Trimmed output:

```json
{
  "result_count": 5,
  "elapsed_ms": 1134,
  "results": [
    {
      "rank": 1,
      "title": "Python Developer jobs in Berlin, Berlin, Germany",
      "url": "https://www.linkedin.com/jobs/python-developer-jobs-berlin?...",
      "source": "brave"
    },
    {
      "rank": 3,
      "title": "Heatle sucht Python backend DevOps in Berlin, ...",
      "url": "https://de.linkedin.com/jobs/view/python-backend-devops-at-heatle-...",
      "source": "brave"
    }
  ]
}
```

Want only LinkedIn Pulse articles, or only company pages? Narrow the `site:`
prefix:

```bash
# Pulse articles
http --ignore-stdin -b GET :8000/api/v1/search \
  q=="site:linkedin.com/pulse python performance" max_results==5

# Company pages
http --ignore-stdin -b GET :8000/api/v1/search \
  q=="site:linkedin.com/company openai" max_results==3
```

### 2. Extract a LinkedIn Pulse article

Pulse articles are article-shaped, so `/extract` works very well on them:

```bash
http --ignore-stdin -b POST :8000/api/v1/extract \
  url="https://www.linkedin.com/pulse/why-engineers-learning-python-koen-van-viegen" \
  | jq '{title, description, language, text_len: (.text | length), preview: .text[:200]}'
```

```json
{
  "title": "Why Engineers Are Learning Python",
  "description": "For the past two months, we have been teaching Python to our colleagues at Royal HaskoningDHV. ...",
  "language": "en",
  "text_len": 4774,
  "preview": "For the past two months, we have been teaching Python to our colleagues at Royal HaskoningDHV. It has been a great experience for me. ..."
}
```

### 3. Extract a LinkedIn company page

Company pages give you the company description, follower count, and the
latest pinned posts:

```bash
http --ignore-stdin -b POST :8000/api/v1/extract \
  url="https://www.linkedin.com/company/openai" \
  | jq '{title, description, text: .text[:300]}'
```

```json
{
  "title": "OpenAI | LinkedIn",
  "description": "OpenAI | 10,903,274 followers on LinkedIn. OpenAI is an AI research and deployment company ...",
  "text": "Today we're launching the OpenAI Deployment Company to help businesses build around intelligence. ..."
}
```

### 4. Discover-then-extract one-liner

Chain it: search for a topic on LinkedIn Pulse, grab the top hit, extract it
to Markdown:

```bash
TOP=$(http --ignore-stdin -b GET :8000/api/v1/search \
        q=="site:linkedin.com/pulse python type hints" max_results==1 \
        | jq -r '.results[0].url')

http --ignore-stdin -b POST :8000/api/v1/extract url="$TOP" | jq -r .markdown
```

### What doesn't work, and why

LinkedIn is hostile to scraping, so be honest about the limits of this
approach:

| Target page                                          | `/extract` works? | Why                                                                                         |
| ---------------------------------------------------- | ----------------- | ------------------------------------------------------------------------------------------- |
| `linkedin.com/pulse/<slug>` (Pulse articles)         | **Yes**           | Article-shaped HTML, readability handles it cleanly.                                        |
| `linkedin.com/company/<slug>` (Company pages)        | **Yes**           | Public landing page with description + posts.                                               |
| `linkedin.com/jobs/<title>-jobs-<location>` (lists)  | Partial           | Shows filter UI text but not individual cards - it's a list page, not an article.           |
| `linkedin.com/jobs/view/<id>` (single job postings)  | **No**            | LinkedIn redirects unauthenticated visitors to a "you've seen all jobs" placeholder.        |
| `linkedin.com/in/<slug>` (profiles)                  | **No**            | Login wall.                                                                                 |

If you specifically need structured job listings, your best bet is to write
your own scraper against LinkedIn's public `jobs-guest` HTML fragment endpoint
and parse the `<li class="result-card">` blocks yourself - the patterns are
the same as Brave/DuckDuckGo, just point a Playwright context at the URL,
grab `page.content()`, and run BeautifulSoup over it. The
[`BrowserManager`](../src/websearch_api/browser/manager.py) class is reusable
for exactly this.

---

## Error responses

Every non-2xx response is a uniform envelope. HTTPie exits with a non-zero code
(`--check-status` enforces this if you want it to fail the script):

### `422 Unprocessable Entity` - validation error

```bash
http POST :8000/api/v1/search query="   "
```

```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body", "query"],
      "msg": "Value error, query must not be empty or whitespace-only"
    }
  ]
}
```

```bash
http POST :8000/api/v1/extract url="not-a-url"
```

```json
{
  "detail": [
    {
      "type": "url_parsing",
      "loc": ["body", "url"],
      "msg": "Input should be a valid URL, relative URL without a base"
    }
  ]
}
```

### `502 Bad Gateway` - upstream blocked or unreachable

Happens when the target rate-limits us (`HTTP 429`) or refuses the connection:

```json
{ "detail": "brave rate-limited the request (429)" }
```

### `504 Gateway Timeout` - target site didn't load in time

Tune `WEBSEARCH_REQUEST_TIMEOUT_MS` if you see this on slow sites:

```json
{ "detail": "https://slow.example.com did not load within 20000ms" }
```

### `503 Service Unavailable` - browser pool not ready

Only seen briefly during server startup before Chromium finishes booting:

```json
{ "detail": "browser pool is not ready" }
```

---

## Tips

- Pretty-print JSON only: `http --ignore-stdin -b POST ... | jq`
- Save a response for replay: `http POST ... > out.json`
- Use a `.httpie/session.json` session file for persistent headers
  (`http --session=ws :8000/...`)
- Pipe huge `text`/`markdown` blobs straight into your LLM of choice with
  `jq -r .markdown | <your llm CLI>`
- Set `WEBSEARCH_BROWSER_HEADLESS=false` before `mise run serve` to watch
  Playwright drive the browser while you call these endpoints
- Anywhere you pipe HTTPie into another command (`| jq`, `| xargs`, `> file`
  is fine, but `command | http ...` and `http ... | command` are different
  stories), remember `--ignore-stdin` on the HTTPie invocation that has
  `key=value` body items
