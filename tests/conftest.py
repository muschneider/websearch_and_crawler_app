"""Shared pytest fixtures.

Notes
-----
* The FastAPI app's ``lifespan`` boots Playwright. For unit tests we don't
  want a real browser, so :func:`client` overrides
  :func:`websearch_api.api.dependencies.get_browser_manager` to return a stub
  that satisfies ``BrowserManager``'s public surface.
* Provider stubs are injected via ``app.dependency_overrides`` so tests can
  assert exactly what the route receives without monkeypatching imports.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from websearch_api.api.dependencies import (
    get_brave,
    get_browser_manager,
    get_duckduckgo,
    get_page_extractor,
)
from websearch_api.config import Settings, get_settings
from websearch_api.main import create_app

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# --------------------------------------------------------------------------- #
# Static HTML fixtures                                                        #
# --------------------------------------------------------------------------- #
@pytest.fixture
def ddg_results_html() -> str:
    return (FIXTURES_DIR / "duckduckgo_results.html").read_text(encoding="utf-8")


@pytest.fixture
def ddg_empty_html() -> str:
    return (FIXTURES_DIR / "duckduckgo_empty.html").read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# Settings + browser stubs                                                    #
# --------------------------------------------------------------------------- #
@pytest.fixture
def settings() -> Settings:
    """Fresh ``Settings`` instance with deterministic defaults for tests."""
    get_settings.cache_clear()
    s = Settings(
        log_level="WARNING",
        default_max_results=5,
        max_results_hard_cap=10,
        request_timeout_ms=5_000,
    )
    return s


class _StubBrowserManager:
    """Stand-in for :class:`BrowserManager` used by API tests.

    The provider stubs we inject never actually touch this object, so we only
    need to satisfy the public surface the dependency-checker inspects.
    """

    is_ready: bool = True

    async def start(self) -> None:  # pragma: no cover - never called in unit tests
        return None

    async def stop(self) -> None:  # pragma: no cover
        return None


# --------------------------------------------------------------------------- #
# FastAPI test client                                                         #
# --------------------------------------------------------------------------- #
@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    """A ``TestClient`` whose browser + providers are stubbed by default.

    The stub is pre-installed on ``app.state`` so the lifespan does NOT launch
    a real Chromium - keeping the unit-test suite fast and dependency-free.
    """
    app = create_app(settings=settings)
    app.state.browser_manager = _StubBrowserManager()

    app.dependency_overrides[get_browser_manager] = lambda: _StubBrowserManager()
    # We override the settings dependency too so the routes see the same object
    # the test created (rather than the lru_cache singleton).
    app.dependency_overrides[get_settings] = lambda: settings

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


@pytest.fixture
def override_provider(client: TestClient):
    """Helper that swaps a provider dependency for a test double.

    Usage::

        def test_foo(client, override_provider):
            override_provider(get_duckduckgo, FakeDDG())
            ...
    """

    def _override(dep, replacement):
        client.app.dependency_overrides[dep] = lambda: replacement

    return _override


@pytest.fixture
def brave_dep_key():
    return get_brave


@pytest.fixture
def duckduckgo_dep_key():
    return get_duckduckgo


@pytest.fixture
def extractor_dep_key():
    return get_page_extractor
