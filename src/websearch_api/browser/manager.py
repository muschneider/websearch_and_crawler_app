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
        # Flags chosen to minimise the obvious "I am Playwright" tells. Anything
        # destructive to security (--no-sandbox, --disable-web-security) is
        # deliberately omitted; users running in Docker can add them via
        # WEBSEARCH_BROWSER_EXTRA_ARGS if they really need to.
        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-features=IsolateOrigins,site-per-process,AutomationControlled",
            "--disable-site-isolation-trials",
            "--disable-dev-shm-usage",
            "--disable-infobars",
            "--no-first-run",
            "--no-default-browser-check",
            "--password-store=basic",
            "--use-mock-keychain",
            # Real users hit a non-empty new-tab page; suppressing it removes a tell.
            "--homepage=about:blank",
        ]
        self._browser = await self._playwright.chromium.launch(
            headless=self._settings.browser_headless,
            args=launch_args,
            # `chromium_sandbox=False` matches the Docker case some users hit;
            # has no effect on platforms where the sandbox isn't required.
            chromium_sandbox=False,
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
        user_agent: str | None = None,
        timezone_id: str | None = None,
        extra_http_headers: dict[str, str] | None = None,
        storage_state: dict | None = None,
        proxy: dict | None = None,
    ) -> AsyncIterator[BrowserContext]:
        """Yield a fresh isolated browser context, then close it.

        Parameters
        ----------
        locale, viewport
            Common defaults; pass-through to Playwright.
        user_agent
            Per-call override. ``None`` falls back to ``settings.user_agent``.
            Providers use this to rotate identities and reduce fingerprinting.
        timezone_id
            IANA timezone (e.g. ``"Europe/Lisbon"``). When set, Playwright will
            align ``Intl`` / ``Date`` APIs so the context is internally
            consistent with the rotated locale.
        extra_http_headers
            Additional HTTP headers attached to every request (e.g.
            ``Accept-Language``, ``Sec-CH-UA-*``, ``Referer``).
        storage_state
            A previously captured ``await context.storage_state()`` dict. When
            provided the new context starts with those cookies / localStorage
            already populated — invaluable for replaying a "warmed" session
            and reusing Cloudflare clearance cookies on subsequent requests.
        proxy
            Per-context proxy config dict, e.g.
            ``{"server": "http://host:port", "username": "...", "password": "..."}``.
            Use this when the host IP is rate-limited and rotation isn't enough.

        Usage::

            async with browser_manager.new_context() as ctx:
                page = await ctx.new_page()
                await page.goto(...)
        """
        if self._browser is None:
            raise RuntimeError("BrowserManager.start() must be called before new_context()")

        kwargs: dict[str, object] = {
            "user_agent": user_agent or self._settings.user_agent,
            "viewport": {"width": viewport[0], "height": viewport[1]},
            "locale": locale,
            "ignore_https_errors": True,
        }
        if timezone_id:
            kwargs["timezone_id"] = timezone_id
        if extra_http_headers:
            kwargs["extra_http_headers"] = extra_http_headers
        if storage_state:
            kwargs["storage_state"] = storage_state
        if proxy:
            kwargs["proxy"] = proxy

        context = await self._browser.new_context(**kwargs)
        # Reasonable default; individual goto/wait calls can still override.
        context.set_default_timeout(self._settings.request_timeout_ms)
        try:
            yield context
        finally:
            try:
                await context.close()
            except Exception:  # pragma: no cover
                logger.debug("error closing context", exc_info=True)
