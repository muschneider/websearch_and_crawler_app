"""Process-wide Playwright lifecycle.

Starting Chromium costs ~300-800 ms and consumes meaningful memory. We therefore
launch a **single** browser instance for the lifetime of the FastAPI process and
hand out fresh :class:`~playwright.async_api.BrowserContext` objects per request.
Contexts are cheap to create, fully isolate cookies/storage, and let us tune
viewport, user agent, and locale on a per-call basis.

The manager is safe to use from multiple concurrent requests because each call
to :meth:`new_context` returns an independent context.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from playwright.async_api import Browser, Playwright, async_playwright

from websearch_api.config import Settings

if TYPE_CHECKING:
    from playwright.async_api import BrowserContext

logger = logging.getLogger(__name__)


class BrowserManager:
    """Owns the Playwright + Chromium process for the app's lifetime."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None

    # ------------------------------------------------------------------ #
    # lifecycle                                                          #
    # ------------------------------------------------------------------ #
    async def start(self) -> None:
        """Launch Playwright + Chromium. Safe to call multiple times (no-op)."""
        if self._browser is not None:
            return

        logger.info("starting playwright + chromium (headless=%s)", self._settings.browser_headless)
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self._settings.browser_headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ],
        )
        logger.info("chromium ready: %s", self._browser.version)

    async def stop(self) -> None:
        """Tear everything down. Safe to call when already stopped."""
        if self._browser is not None:
            try:
                await self._browser.close()
            except Exception:  # pragma: no cover - best-effort shutdown
                logger.warning("error closing browser", exc_info=True)
            self._browser = None

        if self._playwright is not None:
            try:
                await self._playwright.stop()
            except Exception:  # pragma: no cover
                logger.warning("error stopping playwright", exc_info=True)
            self._playwright = None

        logger.info("browser stopped")

    # ------------------------------------------------------------------ #
    # introspection                                                      #
    # ------------------------------------------------------------------ #
    @property
    def is_ready(self) -> bool:
        return self._browser is not None and self._browser.is_connected()

    # ------------------------------------------------------------------ #
    # context factory                                                    #
    # ------------------------------------------------------------------ #
    @asynccontextmanager
    async def new_context(
        self,
        *,
        locale: str = "en-US",
        viewport: tuple[int, int] = (1366, 768),
    ) -> AsyncIterator[BrowserContext]:
        """Yield a fresh isolated browser context, then close it.

        Usage::

            async with browser_manager.new_context() as ctx:
                page = await ctx.new_page()
                await page.goto(...)
        """
        if self._browser is None:
            raise RuntimeError("BrowserManager.start() must be called before new_context()")

        context = await self._browser.new_context(
            user_agent=self._settings.user_agent,
            viewport={"width": viewport[0], "height": viewport[1]},
            locale=locale,
            ignore_https_errors=True,
        )
        # Reasonable default; individual goto/wait calls can still override.
        context.set_default_timeout(self._settings.request_timeout_ms)
        try:
            yield context
        finally:
            try:
                await context.close()
            except Exception:  # pragma: no cover
                logger.debug("error closing context", exc_info=True)
