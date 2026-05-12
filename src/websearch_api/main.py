"""FastAPI application entry point.

This module wires together configuration, logging, the browser lifecycle, and
the HTTP routers. It deliberately stays thin so that the application can be
imported (``websearch_api.main:app``) by both ``uvicorn`` and tests without
side effects beyond logging configuration.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from websearch_api import __version__
from websearch_api.api.routes import api_router, root_router
from websearch_api.browser.manager import BrowserManager
from websearch_api.config import Settings, get_settings
from websearch_api.exceptions import (
    InvalidQueryError,
    ProviderBlockedError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from websearch_api.logging_config import configure_logging
from websearch_api.models import ErrorResponse

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Boot the browser on startup, tear it down on shutdown.

    Tests can pre-populate ``app.state.browser_manager`` before entering
    ``TestClient``; in that case we don't launch a real Chromium and we don't
    take ownership of shutdown.
    """
    settings: Settings = get_settings()
    configure_logging(level=settings.log_level, fmt=settings.log_format)
    logger.info("starting websearch-api %s", __version__)

    owned = False
    if getattr(app.state, "browser_manager", None) is None:
        manager = BrowserManager(settings)
        await manager.start()
        app.state.browser_manager = manager
        owned = True

    try:
        yield
    finally:
        logger.info("shutting down websearch-api")
        if owned:
            await app.state.browser_manager.stop()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Application factory.

    Useful for tests, which can call ``create_app()`` and then override
    dependencies *before* lifespan runs.
    """
    settings = settings or get_settings()
    configure_logging(level=settings.log_level, fmt=settings.log_format)

    app = FastAPI(
        title="websearch-api",
        version=__version__,
        description=(
            "A Tavily-like web search + page-extract HTTP service backed by "
            "Playwright.\n\n"
            "* `POST /api/v1/search` runs a generic web search.\n"
            "* `POST /api/v1/extract` fetches a URL and returns its cleaned "
            "main-content text, Markdown, links, and metadata.\n"
        ),
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(root_router)
    app.include_router(api_router)

    _register_exception_handlers(app)
    return app


def _register_exception_handlers(app: FastAPI) -> None:
    """Translate domain exceptions into uniform JSON error envelopes."""

    @app.exception_handler(InvalidQueryError)
    async def _invalid_query(_: Request, exc: InvalidQueryError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content=ErrorResponse(error="invalid_query", detail=str(exc)).model_dump(),
        )

    @app.exception_handler(ProviderTimeoutError)
    async def _timeout(_: Request, exc: ProviderTimeoutError) -> JSONResponse:
        return JSONResponse(
            status_code=504,
            content=ErrorResponse(error="provider_timeout", detail=str(exc)).model_dump(),
        )

    @app.exception_handler(ProviderBlockedError)
    async def _blocked(_: Request, exc: ProviderBlockedError) -> JSONResponse:
        return JSONResponse(
            status_code=502,
            content=ErrorResponse(error="provider_blocked", detail=str(exc)).model_dump(),
        )

    @app.exception_handler(ProviderUnavailableError)
    async def _unavailable(_: Request, exc: ProviderUnavailableError) -> JSONResponse:
        return JSONResponse(
            status_code=502,
            content=ErrorResponse(error="provider_unavailable", detail=str(exc)).model_dump(),
        )


# Eagerly instantiate at import time so `uvicorn websearch_api.main:app` works.
app = create_app()
