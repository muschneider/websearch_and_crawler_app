"""Domain exceptions raised by the search providers.

These exceptions are deliberately decoupled from HTTP semantics. The API layer
(:mod:`websearch_api.api.routes`) translates each one into an appropriate
status code via exception handlers registered on the FastAPI app.
"""

from __future__ import annotations


class SearchError(Exception):
    """Base class for all search-related failures."""


class InvalidQueryError(SearchError):
    """The supplied query is empty or otherwise malformed."""


class ProviderTimeoutError(SearchError):
    """The upstream provider did not respond within the configured timeout."""


class ProviderUnavailableError(SearchError):
    """The upstream provider returned an unexpected response or could not be reached."""


class ProviderBlockedError(ProviderUnavailableError):
    """The upstream provider actively blocked the request (captcha, 4xx, etc.)."""
