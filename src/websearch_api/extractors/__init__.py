"""Page extractors - take an arbitrary URL, return structured content.

Currently a single Playwright-backed implementation lives here; the module is
laid out so other strategies (e.g. an http-only fast path) can slot in later.
"""

from __future__ import annotations

from websearch_api.extractors.page import PageExtractor

__all__ = ["PageExtractor"]
