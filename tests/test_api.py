"""HTTP-layer tests using FastAPI's TestClient with stubbed providers.

These tests never touch a real browser or the network; they verify that:

* Request validation rejects bad input with 422 / 400.
* Domain exceptions are translated into the right HTTP status codes.
* Successful responses match the documented JSON envelope shape.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import AnyHttpUrl

from websearch_api.exceptions import (
    ProviderBlockedError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from websearch_api.models import SearchResult


# --------------------------------------------------------------------------- #
# Provider doubles                                                            #
# --------------------------------------------------------------------------- #
class _FakeWebProvider:
    """Stand-in for any ``SearchProvider`` (Brave / DuckDuckGo) used in tests."""

    def __init__(
        self,
        name: str = "brave",
        results: list[SearchResult] | None = None,
        raise_exc: Exception | None = None,
    ) -> None:
        self.name = name
        self._results = results or []
        self._raise = raise_exc
        self.calls: list[tuple[str, int]] = []

    async def search(self, query: str, *, max_results: int) -> list[SearchResult]:
        self.calls.append((query, max_results))
        if self._raise:
            raise self._raise
        return self._results[:max_results]


# --------------------------------------------------------------------------- #
# Fixture helpers                                                             #
# --------------------------------------------------------------------------- #
def _sample_result(rank: int = 1, source: str = "brave") -> SearchResult:
    return SearchResult(
        title=f"Example #{rank}",
        url=AnyHttpUrl(f"https://example.com/{rank}"),
        snippet=f"snippet {rank}",
        rank=rank,
        source=source,
        metadata={"k": "v"},
    )


# --------------------------------------------------------------------------- #
# Health / providers                                                          #
# --------------------------------------------------------------------------- #
def test_health_returns_ok(client) -> None:
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["browser_ready"] is True
    assert "version" in body


def test_providers_endpoint_lists_known_backends(client) -> None:
    r = client.get("/api/v1/providers")
    assert r.status_code == 200
    assert set(r.json()["providers"]) == {"brave", "duckduckgo"}


def test_root_redirects_to_docs(client) -> None:
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 307
    assert r.headers["location"] == "/docs"


# --------------------------------------------------------------------------- #
# /search                                                                     #
# --------------------------------------------------------------------------- #
def test_post_search_returns_structured_envelope(
    client, override_provider, duckduckgo_dep_key
) -> None:
    fake = _FakeWebProvider(
        name="duckduckgo",
        results=[_sample_result(1, "duckduckgo"), _sample_result(2, "duckduckgo")],
    )
    override_provider(duckduckgo_dep_key, fake)

    r = client.post(
        "/api/v1/search", json={"query": "python", "max_results": 5, "provider": "duckduckgo"}
    )
    assert r.status_code == 200, r.text

    body = r.json()
    assert body["query"] == "python"
    assert body["provider"] == "duckduckgo"
    assert body["result_count"] == 2
    assert body["elapsed_ms"] >= 0
    assert "fetched_at" in body
    assert len(body["results"]) == 2

    first = body["results"][0]
    assert first == {
        "title": "Example #1",
        "url": "https://example.com/1",
        "snippet": "snippet 1",
        "rank": 1,
        "source": "duckduckgo",
        "metadata": {"k": "v"},
    }

    # The provider was called exactly once with the trimmed query.
    assert fake.calls == [("python", 5)]


def test_get_search_query_variant(client, override_provider, duckduckgo_dep_key) -> None:
    fake = _FakeWebProvider(results=[_sample_result(1)])
    override_provider(duckduckgo_dep_key, fake)

    r = client.get("/api/v1/search", params={"q": "fastapi", "provider": "duckduckgo"})
    assert r.status_code == 200
    assert r.json()["result_count"] == 1
    assert fake.calls[0][0] == "fastapi"


def test_search_empty_query_returns_422(client) -> None:
    r = client.post("/api/v1/search", json={"query": "   "})
    assert r.status_code == 422
    # Pydantic returns its standard error envelope here.
    assert "detail" in r.json()


def test_search_empty_results_returns_200(client, override_provider, duckduckgo_dep_key) -> None:
    override_provider(duckduckgo_dep_key, _FakeWebProvider(results=[]))

    r = client.post("/api/v1/search", json={"query": "asdkjhasdkjhasd", "provider": "duckduckgo"})
    assert r.status_code == 200
    body = r.json()
    assert body["result_count"] == 0
    assert body["results"] == []


@pytest.mark.parametrize(
    ("exc", "expected_status"),
    [
        (ProviderTimeoutError("slow"), 504),
        (ProviderBlockedError("captcha"), 502),
        (ProviderUnavailableError("oops"), 502),
    ],
)
def test_search_translates_provider_errors(
    client, override_provider, duckduckgo_dep_key, exc, expected_status
) -> None:
    override_provider(duckduckgo_dep_key, _FakeWebProvider(raise_exc=exc))

    r = client.post("/api/v1/search", json={"query": "boom", "provider": "duckduckgo"})
    assert r.status_code == expected_status
    body = r.json()
    # Body shape depends on whether HTTPException was raised inside the route
    # or our global handler intercepted the domain exception first. Both paths
    # set a non-empty diagnostic in either ``detail`` or ``detail``/``error``.
    assert body.get("detail") or body.get("error")


# --------------------------------------------------------------------------- #
# Unknown provider                                                            #
# --------------------------------------------------------------------------- #
def test_unknown_provider_rejected(client) -> None:
    r = client.post("/api/v1/search", json={"query": "x", "provider": "yandex"})
    # Pydantic rejects this at the request-body validation stage (422).
    assert r.status_code == 422


# --------------------------------------------------------------------------- #
# /extract                                                                    #
# --------------------------------------------------------------------------- #
class _FakeExtractor:
    """Stand-in PageExtractor that returns a canned dict and records calls."""

    def __init__(
        self,
        payload: dict[str, Any] | None = None,
        raise_exc: Exception | None = None,
    ) -> None:
        self._payload = payload
        self._raise = raise_exc
        self.calls: list[dict[str, Any]] = []

    async def extract(
        self,
        url: str,
        *,
        wait_for_selector: str | None = None,
        include_html: bool = False,
        include_links: bool = True,
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "url": url,
                "wait_for_selector": wait_for_selector,
                "include_html": include_html,
                "include_links": include_links,
            }
        )
        if self._raise:
            raise self._raise
        return self._payload or _sample_extract_payload()


def _sample_extract_payload(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "status_code": 200,
        "final_url": "https://blog.example.com/post/",
        "title": "Sample Page",
        "description": "A short blurb.",
        "author": None,
        "language": "en",
        "site_name": "Example",
        "published_at": None,
        "text": "Hello world body text.",
        "markdown": "# Sample Page\n\nHello world body text.",
        "html": None,
        "links": [
            {
                "text": "more",
                "url": AnyHttpUrl("https://blog.example.com/more"),
                "rel": None,
            }
        ],
        "metadata": {"canonical": "https://blog.example.com/post/"},
    }
    base.update(overrides)
    return base


def test_post_extract_returns_flat_envelope(client, override_provider, extractor_dep_key) -> None:
    fake = _FakeExtractor()
    override_provider(extractor_dep_key, fake)

    r = client.post(
        "/api/v1/extract",
        json={"url": "https://blog.example.com/post"},
    )
    assert r.status_code == 200, r.text

    body = r.json()
    # Request fields echoed.
    assert body["url"] == "https://blog.example.com/post"
    assert body["final_url"] == "https://blog.example.com/post/"
    assert body["status_code"] == 200
    assert body["elapsed_ms"] >= 0
    assert "fetched_at" in body

    # Content fields.
    assert body["title"] == "Sample Page"
    assert body["description"] == "A short blurb."
    assert body["language"] == "en"
    assert body["text"] == "Hello world body text."
    assert body["markdown"].startswith("# Sample Page")
    assert body["html"] is None
    assert body["links"][0]["url"] == "https://blog.example.com/more"
    assert body["metadata"]["canonical"] == "https://blog.example.com/post/"

    # Provider was called once with the right options.
    assert fake.calls == [
        {
            "url": "https://blog.example.com/post",
            "wait_for_selector": None,
            "include_html": False,
            "include_links": True,
        }
    ]


def test_post_extract_forwards_options(client, override_provider, extractor_dep_key) -> None:
    fake = _FakeExtractor(payload=_sample_extract_payload(html="<div>ok</div>"))
    override_provider(extractor_dep_key, fake)

    r = client.post(
        "/api/v1/extract",
        json={
            "url": "https://blog.example.com/post",
            "wait_for_selector": "main.article",
            "include_html": True,
            "include_links": False,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["html"] == "<div>ok</div>"
    assert fake.calls[0]["wait_for_selector"] == "main.article"
    assert fake.calls[0]["include_html"] is True
    assert fake.calls[0]["include_links"] is False


def test_get_extract_query_variant(client, override_provider, extractor_dep_key) -> None:
    fake = _FakeExtractor()
    override_provider(extractor_dep_key, fake)

    r = client.get(
        "/api/v1/extract",
        params={"url": "https://blog.example.com/post", "include_html": "true"},
    )
    assert r.status_code == 200
    assert fake.calls[0]["include_html"] is True


def test_extract_invalid_url_rejected_at_validation(client) -> None:
    r = client.post("/api/v1/extract", json={"url": "not-a-url"})
    assert r.status_code == 422


def test_extract_non_http_url_rejected(client) -> None:
    r = client.post("/api/v1/extract", json={"url": "ftp://example.com/file"})
    assert r.status_code == 422


@pytest.mark.parametrize(
    ("exc", "expected_status"),
    [
        (ProviderTimeoutError("slow"), 504),
        (ProviderBlockedError("429"), 502),
        (ProviderUnavailableError("dead"), 502),
    ],
)
def test_extract_translates_provider_errors(
    client, override_provider, extractor_dep_key, exc, expected_status
) -> None:
    override_provider(extractor_dep_key, _FakeExtractor(raise_exc=exc))

    r = client.post("/api/v1/extract", json={"url": "https://blog.example.com/post"})
    assert r.status_code == expected_status
    body = r.json()
    assert body.get("detail") or body.get("error")
