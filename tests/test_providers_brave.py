"""Unit tests for the Brave Search provider's pure parser and humanisation layer."""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from websearch_api.config import Settings
from websearch_api.exceptions import (
    ProviderBlockedError,
    ProviderUnavailableError,
)
from websearch_api.providers.brave import (
    _PERSONAS,
    BraveSearchProvider,
    _build_stealth_script,
    _chunk_for_typing,
    _compute_backoff_ms,
    _looks_like_block,
    _parse_proxy_url,
    _pick_persona,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def brave_results_html() -> str:
    return (FIXTURES_DIR / "brave_results.html").read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# Pure parser                                                                 #
# --------------------------------------------------------------------------- #
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


# --------------------------------------------------------------------------- #
# Persona pool                                                                #
# --------------------------------------------------------------------------- #
def test_persona_pool_is_non_empty_and_unique() -> None:
    assert len(_PERSONAS) >= 4
    # Every persona must have a UA, and we want at least some UA diversity.
    uas = [p.user_agent for p in _PERSONAS]
    assert all(uas), "every persona must define a non-empty user_agent"
    assert len(set(uas)) >= 3, "expected at least 3 distinct user-agent strings"


def test_persona_chrome_ua_carries_consistent_client_hints() -> None:
    """Chrome/Edge UAs must ship Sec-CH-UA. Firefox UAs must not."""
    for persona in _PERSONAS:
        is_chromium = "Chrome/" in persona.user_agent or "Edg/" in persona.user_agent
        is_firefox = "Firefox/" in persona.user_agent

        if is_chromium:
            assert persona.sec_ch_ua, f"chromium persona missing Sec-CH-UA: {persona.user_agent}"
            headers = persona.extra_http_headers
            assert "Sec-CH-UA" in headers
            assert "Sec-CH-UA-Platform" in headers
            assert "Sec-CH-UA-Mobile" in headers
        elif is_firefox:
            assert persona.sec_ch_ua is None, "firefox does not send Sec-CH-UA"
            assert "Sec-CH-UA" not in persona.extra_http_headers


def test_persona_headers_always_include_accept_language() -> None:
    for persona in _PERSONAS:
        headers = persona.extra_http_headers
        assert headers["Accept-Language"]
        assert headers["Accept"].startswith("text/html")
        assert headers["Sec-Fetch-Mode"] == "navigate"


def test_pick_persona_uses_provided_rng_for_determinism() -> None:
    rng = random.Random(42)
    first = _pick_persona(rng)
    # Reseeding the same rng must reproduce the same choice.
    second = _pick_persona(random.Random(42))
    assert first is second
    assert first in _PERSONAS


# --------------------------------------------------------------------------- #
# Stealth init script                                                         #
# --------------------------------------------------------------------------- #
def test_stealth_script_targets_all_known_fingerprint_vectors() -> None:
    persona = _PERSONAS[0]
    script = _build_stealth_script(persona)

    # Each tweak we promise in the module docstring must appear.
    assert "webdriver" in script
    assert "languages" in script
    assert "plugins" in script
    assert "window.chrome" in script
    assert "Notification.permission" in script
    assert "WebGLRenderingContext" in script

    # The locale array must reflect the persona's locale.
    primary = persona.locale
    base = primary.split("-", 1)[0]
    assert f"'{primary}'" in script
    if primary != base:
        assert f"'{base}'" in script


def test_stealth_script_handles_locale_without_region() -> None:
    """Edge case: a persona with a bare ``'en'`` locale produces a single-item list."""
    persona = _PERSONAS[0]
    # Build a synthetic persona using the same dataclass-shape via copy.
    bare = type(persona)(
        user_agent=persona.user_agent,
        viewport=persona.viewport,
        locale="en",
        timezone_id=persona.timezone_id,
        accept_language="en;q=0.9",
        sec_ch_ua=persona.sec_ch_ua,
        sec_ch_ua_platform=persona.sec_ch_ua_platform,
    )
    script = _build_stealth_script(bare)
    assert "['en']" in script


# --------------------------------------------------------------------------- #
# Backoff                                                                     #
# --------------------------------------------------------------------------- #
def test_backoff_grows_exponentially_and_is_capped() -> None:
    rng = random.Random(0)
    delays = [_compute_backoff_ms(i, base_ms=1_000, max_ms=8_000, rng=rng) for i in range(6)]
    # Expected exponent: 1000, 2000, 4000, 8000, 8000, 8000 (capped).
    # Jitter adds 0-30%, so each value must sit in [exp, exp*1.3].
    expected_min = [1000, 2000, 4000, 8000, 8000, 8000]
    for got, lo in zip(delays, expected_min, strict=True):
        assert lo <= got <= int(lo * 1.3) + 1


def test_backoff_zero_base_returns_zero() -> None:
    rng = random.Random(0)
    assert _compute_backoff_ms(0, base_ms=0, max_ms=8_000, rng=rng) == 0
    assert _compute_backoff_ms(3, base_ms=0, max_ms=8_000, rng=rng) == 0


# --------------------------------------------------------------------------- #
# Retry loop                                                                  #
# --------------------------------------------------------------------------- #
def _settings_for_tests(**overrides: Any) -> Settings:
    """Settings tuned to make retry tests fast and deterministic."""
    base: dict[str, Any] = {
        "log_level": "WARNING",
        "request_timeout_ms": 5_000,
        "brave_retry_attempts": 3,
        "brave_retry_backoff_base_ms": 0,  # no real sleep
        "brave_retry_backoff_max_ms": 0,
        "brave_prenav_jitter_min_ms": 0,
        "brave_prenav_jitter_max_ms": 0,
        # Retry tests target the retry loop, not the homepage flow. Direct-URL
        # navigation keeps the page stub minimal. The homepage flow has its
        # own dedicated test.
        "brave_use_homepage_flow": False,
    }
    base.update(overrides)
    return Settings(**base)


def _make_provider(
    settings: Settings | None = None,
    *,
    page_factory,
) -> BraveSearchProvider:
    """Build a provider whose browser is fully mocked.

    ``page_factory`` is a zero-arg callable returning the next mocked Page.
    We return a new page per ``new_context()`` so retries get a fresh stub.
    """
    s = settings or _settings_for_tests()

    browser = MagicMock()

    class _CtxCM:
        async def __aenter__(self) -> Any:
            ctx = MagicMock()
            ctx.add_init_script = AsyncMock()
            ctx.new_page = AsyncMock(return_value=page_factory())
            ctx.storage_state = AsyncMock(return_value={"cookies": [{"name": "k", "value": "v"}]})
            return ctx

        async def __aexit__(self, *exc_info: object) -> None:
            return None

    browser.new_context = MagicMock(return_value=_CtxCM())

    return BraveSearchProvider(browser=browser, settings=s)


def _stub_page(*, status: int, html: str = "<html></html>") -> MagicMock:
    """Mock Page that supports the direct-URL navigation path."""
    page = MagicMock()
    response = MagicMock()
    response.status = status
    page.goto = AsyncMock(return_value=response)
    page.wait_for_selector = AsyncMock()
    page.content = AsyncMock(return_value=html)
    page.mouse = MagicMock()
    page.mouse.move = AsyncMock()
    page.mouse.wheel = AsyncMock()
    return page


def _stub_page_for_homepage_flow(*, final_html: str) -> MagicMock:
    """Mock Page that supports homepage -> input -> type -> submit -> SERP."""
    page = MagicMock()

    homepage_resp = MagicMock(status=200)
    page.goto = AsyncMock(return_value=homepage_resp)

    input_handle = MagicMock()
    input_handle.click = AsyncMock()
    page.wait_for_selector = AsyncMock(return_value=input_handle)
    page.wait_for_url = AsyncMock()

    page.keyboard = MagicMock()
    page.keyboard.type = AsyncMock()
    page.keyboard.press = AsyncMock()

    page.content = AsyncMock(return_value=final_html)
    page.mouse = MagicMock()
    page.mouse.move = AsyncMock()
    page.mouse.wheel = AsyncMock()
    return page


async def test_search_retries_on_429_then_succeeds(brave_results_html: str) -> None:
    """First attempt 429, second attempt 200 with valid HTML -> success."""
    pages = iter(
        [
            _stub_page(status=429),
            _stub_page(status=200, html=brave_results_html),
        ]
    )
    provider = _make_provider(page_factory=lambda: next(pages))

    results = await provider.search("fastapi", max_results=3)

    assert len(results) == 3
    assert provider._browser.new_context.call_count == 2


async def test_search_raises_after_exhausting_retries() -> None:
    """All attempts hit 429 -> ProviderBlockedError surfaces to the caller."""
    provider = _make_provider(page_factory=lambda: _stub_page(status=429))

    with pytest.raises(ProviderBlockedError):
        await provider.search("anything", max_results=5)

    assert provider._browser.new_context.call_count == 3  # attempts=3


async def test_search_does_not_retry_on_non_429_http_error() -> None:
    """A generic 5xx is unavailability, not a block; surface it as-is."""
    provider = _make_provider(page_factory=lambda: _stub_page(status=500))

    with pytest.raises(ProviderUnavailableError):
        await provider.search("anything", max_results=5)

    # No retries: ProviderUnavailableError exits the loop immediately.
    assert provider._browser.new_context.call_count == 1


async def test_search_retries_on_503_block_gate() -> None:
    """403/503 from search.brave.com is treated as a Cloudflare block and retried."""
    pages = iter(
        [
            _stub_page(status=503),
            _stub_page(status=200, html="<html></html>"),
        ]
    )
    provider = _make_provider(page_factory=lambda: next(pages))

    results = await provider.search("anything", max_results=5)
    assert results == []
    assert provider._browser.new_context.call_count == 2


async def test_search_retries_when_html_looks_like_bot_gate() -> None:
    """A 200 OK body containing the captcha needle counts as blocked."""
    pages = iter(
        [
            _stub_page(status=200, html="<html>Are you human?</html>"),
            _stub_page(status=200, html="<html></html>"),  # empty SERP, but unblocked
        ]
    )
    provider = _make_provider(page_factory=lambda: next(pages))

    results = await provider.search("anything", max_results=5)

    assert results == []
    assert provider._browser.new_context.call_count == 2


async def test_search_caches_storage_state_per_persona(brave_results_html: str) -> None:
    """A successful search captures cookies so the next call replays them."""
    provider = _make_provider(page_factory=lambda: _stub_page(status=200, html=brave_results_html))

    await provider.search("first", max_results=3)

    # Cache populated.
    assert len(provider._persona_state) == 1
    cached = next(iter(provider._persona_state.values()))
    assert cached == {"cookies": [{"name": "k", "value": "v"}]}


async def test_search_evicts_poisoned_state_on_429(brave_results_html: str) -> None:
    """When a 429 happens, the cookies for that persona must be evicted."""
    pages = iter(
        [
            _stub_page(status=429),
            _stub_page(status=200, html=brave_results_html),
        ]
    )
    provider = _make_provider(page_factory=lambda: next(pages))

    await provider.search("anything", max_results=3)

    # Exactly one persona ended successful -> exactly one cache entry.
    assert len(provider._persona_state) == 1


# --------------------------------------------------------------------------- #
# Homepage flow                                                               #
# --------------------------------------------------------------------------- #
async def test_homepage_flow_types_and_submits_query(brave_results_html: str) -> None:
    """Verify the cold-path: homepage navigation, typing, Enter, SERP read."""
    page = _stub_page_for_homepage_flow(final_html=brave_results_html)
    provider = _make_provider(
        settings=_settings_for_tests(
            brave_use_homepage_flow=True,
            brave_keystroke_min_ms=0,
            brave_keystroke_max_ms=0,
        ),
        page_factory=lambda: page,
    )

    results = await provider.search("fastapi tutorial", max_results=3)

    assert len(results) == 3

    # Navigated to the homepage exactly once.
    goto_calls = page.goto.await_args_list
    assert len(goto_calls) == 1
    assert goto_calls[0].args[0] == BraveSearchProvider.HOMEPAGE_URL

    # Typed the query in fragments (chunked) and pressed Enter to submit.
    typed = "".join(call.args[0] for call in page.keyboard.type.await_args_list)
    assert typed == "fastapi tutorial"
    page.keyboard.press.assert_awaited_once_with("Enter")


# --------------------------------------------------------------------------- #
# Query-chunker                                                               #
# --------------------------------------------------------------------------- #
def test_chunk_for_typing_round_trips_query() -> None:
    query = "python async patterns 2026"
    chunks = _chunk_for_typing(query)
    assert "".join(chunks) == query
    # We expect at least a few chunks for a query of this length so the typing
    # rhythm has natural pauses.
    assert len(chunks) >= 3


def test_chunk_for_typing_handles_empty_string() -> None:
    assert _chunk_for_typing("") == []


# --------------------------------------------------------------------------- #
# Proxy parsing                                                               #
# --------------------------------------------------------------------------- #
def test_parse_proxy_url_strips_credentials_into_dict() -> None:
    out = _parse_proxy_url("http://alice:s3cret@proxy.example.com:8080")
    assert out == {
        "server": "http://proxy.example.com:8080",
        "username": "alice",
        "password": "s3cret",
    }


def test_parse_proxy_url_supports_no_auth() -> None:
    out = _parse_proxy_url("socks5://10.0.0.1:1080")
    assert out == {"server": "socks5://10.0.0.1:1080"}


def test_parse_proxy_url_rejects_garbage() -> None:
    with pytest.raises(ValueError):
        _parse_proxy_url("not a url")
