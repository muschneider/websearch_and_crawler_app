"""Abstract base class shared by every search provider."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from websearch_api.browser.manager import BrowserManager
from websearch_api.config import Settings
from websearch_api.models import SearchResult


class SearchProvider(ABC):
    """Contract every search backend must implement.

    Subclasses should keep their HTML parsing in a **pure static method** so it
    can be unit-tested with fixture data, with no live browser required.
    """

    #: Unique slug used in the API (``provider="duckduckgo"`` etc).
    name: ClassVar[str]

    def __init__(self, browser: BrowserManager, settings: Settings) -> None:
        self._browser = browser
        self._settings = settings

    @abstractmethod
    async def search(self, query: str, *, max_results: int) -> list[SearchResult]:
        """Execute ``query`` and return up to ``max_results`` structured rows."""
        raise NotImplementedError

    # ------------------------------------------------------------------ #
    # helpers shared by concrete providers                               #
    # ------------------------------------------------------------------ #
    def _clamp(self, requested: int | None) -> int:
        """Apply server-side caps to a caller-supplied ``max_results``."""
        default = self._settings.default_max_results
        cap = self._settings.max_results_hard_cap
        return min(requested or default, cap)
