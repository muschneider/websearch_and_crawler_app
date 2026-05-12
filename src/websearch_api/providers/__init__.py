"""Search providers - swap implementations by registering new subclasses here.

To add a new provider:

1. Subclass :class:`~websearch_api.providers.base.SearchProvider`.
2. Implement ``name`` and the async ``search()`` method.
3. Register it in :data:`PROVIDER_REGISTRY` below so the API layer picks it up.
"""

from __future__ import annotations

from websearch_api.providers.base import SearchProvider
from websearch_api.providers.brave import BraveSearchProvider
from websearch_api.providers.duckduckgo import DuckDuckGoProvider

PROVIDER_REGISTRY: dict[str, type[SearchProvider]] = {
    BraveSearchProvider.name: BraveSearchProvider,
    DuckDuckGoProvider.name: DuckDuckGoProvider,
}

__all__ = [
    "PROVIDER_REGISTRY",
    "BraveSearchProvider",
    "DuckDuckGoProvider",
    "SearchProvider",
]
