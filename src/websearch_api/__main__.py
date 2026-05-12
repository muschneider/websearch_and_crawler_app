"""Allow ``python -m websearch_api`` and the ``websearch-api`` console script.

Both invocations launch the FastAPI app under uvicorn, respecting the
``WEBSEARCH_HOST`` / ``WEBSEARCH_PORT`` environment variables.
"""

from __future__ import annotations

import uvicorn

from websearch_api.config import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "websearch_api.main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        reload=False,
    )


if __name__ == "__main__":  # pragma: no cover
    main()
