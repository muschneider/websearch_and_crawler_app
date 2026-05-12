"""Pydantic request/response models exposed by the HTTP API.

Keeping these in a single module makes them easy to reuse across routes, tests,
and example scripts. They also drive the auto-generated OpenAPI schema served
at ``/docs`` and ``/redoc``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator

ProviderName = Literal["brave", "duckduckgo"]


# --------------------------------------------------------------------------- #
# Generic web-search models                                                   #
# --------------------------------------------------------------------------- #
class SearchResult(BaseModel):
    """A single result row returned by a search provider."""

    model_config = ConfigDict(populate_by_name=True)

    title: str = Field(..., description="Page or document title.")
    url: AnyHttpUrl = Field(..., description="Canonical URL for the result.")
    snippet: str | None = Field(
        default=None,
        description="Short textual excerpt extracted from the result.",
    )
    rank: int = Field(..., ge=1, description="1-based position in the SERP.")
    source: str = Field(..., description="Provider that produced this result.")
    metadata: dict[str, str] = Field(
        default_factory=dict,
        description="Provider-specific extras (e.g. published_at, favicon).",
    )


class SearchRequest(BaseModel):
    """Body for ``POST /api/v1/search``."""

    query: Annotated[str, Field(min_length=1, max_length=512)] = Field(
        ..., description="Free-text search query."
    )
    max_results: int | None = Field(
        default=None,
        ge=1,
        le=100,
        description="Maximum number of results to return. Capped by server config.",
    )
    provider: ProviderName = Field(
        default="brave",
        description=(
            "Search provider to use. `brave` is the default (most reliable from "
            "automation). `duckduckgo` is best-effort - DDG aggressively "
            "challenges headless traffic and may return empty results."
        ),
    )

    @field_validator("query")
    @classmethod
    def _strip_query(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("query must not be empty or whitespace-only")
        return stripped


class SearchResponse(BaseModel):
    """Envelope returned by every search endpoint."""

    query: str
    provider: ProviderName
    result_count: int
    elapsed_ms: int = Field(..., description="Total server-side wall-clock time.")
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    results: list[SearchResult]


# --------------------------------------------------------------------------- #
# Page-extraction models                                                      #
# --------------------------------------------------------------------------- #
class PageLink(BaseModel):
    """One anchor tag harvested from an extracted page."""

    text: str = Field(..., description="Visible link text (whitespace-collapsed).")
    url: AnyHttpUrl = Field(..., description="Absolute target URL (resolved against the page).")
    rel: str | None = Field(
        default=None,
        description="Value of the ``rel`` attribute when present (e.g. 'nofollow ugc').",
    )


class ExtractRequest(BaseModel):
    """Body for ``POST /api/v1/extract``."""

    url: AnyHttpUrl = Field(..., description="Absolute URL to fetch and extract.")
    wait_for_selector: str | None = Field(
        default=None,
        max_length=256,
        description=(
            "Optional CSS selector to wait for before snapshotting the page. "
            "Useful for SPAs that hydrate content client-side."
        ),
    )
    include_html: bool = Field(
        default=False,
        description="If true, include the cleaned main-content HTML in the response.",
    )
    include_links: bool = Field(
        default=True,
        description="If true, include the extracted list of outbound links.",
    )


class ExtractResponse(BaseModel):
    """Flat envelope returned by ``POST /api/v1/extract``.

    Inspired by Tavily's ``/extract``: title + cleaned text + markdown + links
    + metadata in a single JSON payload, no nesting required.
    """

    url: AnyHttpUrl = Field(..., description="URL the caller requested.")
    final_url: AnyHttpUrl = Field(..., description="URL actually reached after any redirects.")
    status_code: int = Field(..., ge=100, le=599, description="HTTP status of the fetch.")
    elapsed_ms: int = Field(..., ge=0, description="Total server-side wall-clock time.")
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    title: str | None = Field(default=None, description="Page title (<title> or og:title).")
    description: str | None = Field(
        default=None, description="Meta description or og:description, if present."
    )
    author: str | None = Field(default=None, description="Author meta tag, if present.")
    language: str | None = Field(
        default=None, description="Page language (lang attribute or og:locale)."
    )
    site_name: str | None = Field(default=None, description="og:site_name, if present.")
    published_at: str | None = Field(
        default=None,
        description="Publication date string from article metadata, if present.",
    )

    text: str = Field(..., description="Cleaned main-content plain text.")
    markdown: str = Field(..., description="Cleaned main-content rendered as Markdown.")
    html: str | None = Field(
        default=None,
        description="Cleaned main-content HTML. Only present when 'include_html' was true.",
    )
    links: list[PageLink] = Field(
        default_factory=list,
        description="Outbound links found in the main content. Empty when 'include_links' is false.",
    )
    metadata: dict[str, str] = Field(
        default_factory=dict,
        description="Misc page metadata (og:image, canonical, favicon, etc.).",
    )


# --------------------------------------------------------------------------- #
# Health / error models                                                       #
# --------------------------------------------------------------------------- #
class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"] = "ok"
    version: str
    browser_ready: bool


class ErrorResponse(BaseModel):
    """Uniform error payload returned for any non-2xx response."""

    error: str = Field(..., description="Machine-readable error code, e.g. 'invalid_query'.")
    detail: str = Field(..., description="Human-readable explanation.")
