"""FastAPI dependency-injection wiring.

The :class:`~websearch_api.browser.BrowserManager` is created once during the
lifespan of the application and stored on ``app.state``. The dependency
functions in this module pull that singleton out of state, instantiate
providers on demand, and hand them to the route handlers.

This keeps the routes themselves free of construction logic and makes mocking
trivial in tests (just override ``app.dependency_overrides[...]``).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from websearch_api.browser.manager import BrowserManager
from websearch_api.config import Settings, get_settings
from websearch_api.extractors import PageExtractor
from websearch_api.providers import (
    PROVIDER_REGISTRY,
    BraveSearchProvider,
    DuckDuckGoProvider,
    SearchProvider,
)


def get_browser_manager(request: Request) -> BrowserManager:
    manager: BrowserManager | None = getattr(request.app.state, "browser_manager", None)
    if manager is None or not manager.is_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="browser pool is not ready",
        )
    return manager


SettingsDep = Annotated[Settings, Depends(get_settings)]
BrowserDep = Annotated[BrowserManager, Depends(get_browser_manager)]


def get_provider(
    name: str,
    browser: BrowserDep,
    settings: SettingsDep,
) -> SearchProvider:
    provider_cls = PROVIDER_REGISTRY.get(name)
    if provider_cls is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"unknown provider: {name!r}",
        )
    return provider_cls(browser=browser, settings=settings)


def get_brave(browser: BrowserDep, settings: SettingsDep) -> BraveSearchProvider:
    return BraveSearchProvider(browser=browser, settings=settings)


def get_duckduckgo(browser: BrowserDep, settings: SettingsDep) -> DuckDuckGoProvider:
    return DuckDuckGoProvider(browser=browser, settings=settings)


def get_page_extractor(browser: BrowserDep, settings: SettingsDep) -> PageExtractor:
    return PageExtractor(browser=browser, settings=settings)


BraveDep = Annotated[BraveSearchProvider, Depends(get_brave)]
DuckDuckGoDep = Annotated[DuckDuckGoProvider, Depends(get_duckduckgo)]
PageExtractorDep = Annotated[PageExtractor, Depends(get_page_extractor)]
