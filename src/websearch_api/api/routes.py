"""HTTP routes exposed by the service.

Endpoints
---------
* ``GET  /``                       - redirect to interactive docs.
* ``GET  /api/v1/health``          - liveness probe + browser readiness.
* ``GET  /api/v1/providers``       - list configured search providers.
* ``POST /api/v1/search``          - structured-body web search.
* ``GET  /api/v1/search``          - URL-query convenience variant.
* ``POST /api/v1/extract``         - fetch a URL and return structured content.
* ``GET  /api/v1/extract``         - URL-query convenience variant of /extract.
"""

from __future__ import annotations

import logging
import time
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import RedirectResponse

from websearch_api import __version__
from websearch_api.api.dependencies import (
    BraveDep,
    BrowserDep,
    DuckDuckGoDep,
    PageExtractorDep,
    SettingsDep,
)
from websearch_api.exceptions import (
    InvalidQueryError,
    ProviderBlockedError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from websearch_api.models import (
    ExtractRequest,
    ExtractResponse,
    HealthResponse,
    ProviderName,
    SearchRequest,
    SearchResponse,
)
from websearch_api.providers.base import SearchProvider

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Routers                                                                     #
# --------------------------------------------------------------------------- #
root_router = APIRouter()
api_router = APIRouter(prefix="/api/v1", tags=["search"])


# --------------------------------------------------------------------------- #
# Root / docs redirect                                                        #
# --------------------------------------------------------------------------- #
@root_router.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    """Send curious humans to the Swagger UI."""
    return RedirectResponse(url="/docs", status_code=status.HTTP_307_TEMPORARY_REDIRECT)


# --------------------------------------------------------------------------- #
# Health / metadata                                                           #
# --------------------------------------------------------------------------- #
@api_router.get(
    "/health",
    response_model=HealthResponse,
    tags=["meta"],
    summary="Liveness probe",
)
async def health(browser: BrowserDep) -> HealthResponse:
    return HealthResponse(
        status="ok" if browser.is_ready else "degraded",
        version=__version__,
        browser_ready=browser.is_ready,
    )


@api_router.get(
    "/providers",
    tags=["meta"],
    summary="List configured providers",
)
async def list_providers() -> dict[str, list[str]]:
    from websearch_api.providers import PROVIDER_REGISTRY

    return {"providers": sorted(PROVIDER_REGISTRY.keys())}


# --------------------------------------------------------------------------- #
# Generic web search                                                          #
# --------------------------------------------------------------------------- #
@api_router.post(
    "/search",
    response_model=SearchResponse,
    summary="Run a web search and return structured results",
)
async def search(
    body: SearchRequest,
    brave: BraveDep,
    duckduckgo: DuckDuckGoDep,
    settings: SettingsDep,
) -> SearchResponse:
    # All providers are injected via FastAPI deps so tests can override them
    # through ``app.dependency_overrides``. Construction is cheap (no I/O), so
    # creating the unused ones per request is fine.
    providers: dict[str, SearchProvider] = {
        "brave": brave,
        "duckduckgo": duckduckgo,
    }
    provider = providers[body.provider]

    start = time.perf_counter()
    try:
        results = await provider.search(
            body.query, max_results=body.max_results or settings.default_max_results
        )
    except InvalidQueryError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ProviderTimeoutError as exc:
        raise HTTPException(status.HTTP_504_GATEWAY_TIMEOUT, detail=str(exc)) from exc
    except ProviderBlockedError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except ProviderUnavailableError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    elapsed = int((time.perf_counter() - start) * 1000)
    logger.info(
        "search.completed",
        extra={
            "query": body.query,
            "provider": body.provider,
            "result_count": len(results),
            "elapsed_ms": elapsed,
        },
    )
    return SearchResponse(
        query=body.query,
        provider=body.provider,
        result_count=len(results),
        elapsed_ms=elapsed,
        results=results,
    )


@api_router.get(
    "/search",
    response_model=SearchResponse,
    summary="Convenience GET variant of /search",
)
async def search_via_query(
    brave: BraveDep,
    duckduckgo: DuckDuckGoDep,
    settings: SettingsDep,
    q: Annotated[
        str,
        Query(min_length=1, max_length=512, description="Search query."),
    ],
    max_results: Annotated[int | None, Query(ge=1, le=100)] = None,
    provider: Annotated[ProviderName, Query()] = "brave",
) -> SearchResponse:
    body = SearchRequest(query=q, max_results=max_results, provider=provider)
    return await search(
        body,
        brave=brave,
        duckduckgo=duckduckgo,
        settings=settings,
    )


# --------------------------------------------------------------------------- #
# Single-URL extract (crawler)                                                #
# --------------------------------------------------------------------------- #
@api_router.post(
    "/extract",
    response_model=ExtractResponse,
    summary="Fetch a URL and return its structured content",
)
async def extract(
    body: ExtractRequest,
    extractor: PageExtractorDep,
) -> ExtractResponse:
    start = time.perf_counter()
    try:
        parsed = await extractor.extract(
            str(body.url),
            wait_for_selector=body.wait_for_selector,
            include_html=body.include_html,
            include_links=body.include_links,
        )
    except ProviderTimeoutError as exc:
        raise HTTPException(status.HTTP_504_GATEWAY_TIMEOUT, detail=str(exc)) from exc
    except ProviderBlockedError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except ProviderUnavailableError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    elapsed = int((time.perf_counter() - start) * 1000)
    logger.info(
        "extract.completed",
        extra={
            "url": str(body.url),
            "status_code": parsed.get("status_code"),
            "elapsed_ms": elapsed,
            "text_len": len(parsed.get("text", "")),
        },
    )
    return ExtractResponse(
        url=body.url,
        elapsed_ms=elapsed,
        **parsed,
    )


@api_router.get(
    "/extract",
    response_model=ExtractResponse,
    summary="Convenience GET variant of /extract",
)
async def extract_via_query(
    extractor: PageExtractorDep,
    url: Annotated[str, Query(min_length=1, max_length=2048, description="URL to extract.")],
    wait_for_selector: Annotated[
        str | None, Query(max_length=256, description="CSS selector to wait for.")
    ] = None,
    include_html: Annotated[bool, Query(description="Include cleaned HTML body.")] = False,
    include_links: Annotated[bool, Query(description="Include extracted links.")] = True,
) -> ExtractResponse:
    body = ExtractRequest(
        url=url,
        wait_for_selector=wait_for_selector,
        include_html=include_html,
        include_links=include_links,
    )
    return await extract(body, extractor=extractor)
