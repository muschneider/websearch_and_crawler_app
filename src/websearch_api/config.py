"""Application configuration loaded from environment variables / .env."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """All runtime configuration for the service.

    Values are read (in order of precedence) from:
      1. Process environment variables prefixed with ``WEBSEARCH_``
      2. A local ``.env`` file at the project root
      3. The defaults defined here
    """

    model_config = SettingsConfigDict(
        env_prefix="WEBSEARCH_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- HTTP server ---
    host: str = "0.0.0.0"
    port: int = 8000

    # --- Logging ---
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_format: Literal["text", "json"] = "text"

    # --- Browser ---
    browser_headless: bool = True
    request_timeout_ms: int = Field(default=20_000, ge=1_000, le=120_000)
    user_agent: str = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )

    # --- Search defaults ---
    default_max_results: int = Field(default=10, ge=1, le=100)
    max_results_hard_cap: int = Field(default=50, ge=1, le=200)

    # --- API ---
    # ``NoDecode`` tells pydantic-settings not to try ``json.loads`` on this
    # field, so we can accept a plain comma-separated string from the env.
    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["*"])

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors(cls, value: object) -> object:
        """Allow ``WEBSEARCH_CORS_ORIGINS`` to be a comma-separated string in env."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("max_results_hard_cap")
    @classmethod
    def _hard_cap_gte_default(cls, value: int, info) -> int:
        default = info.data.get("default_max_results", 10)
        if value < default:
            raise ValueError(
                f"max_results_hard_cap must be >= default_max_results (got {value} < {default})"
            )
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton ``Settings`` instance.

    Cached so that environment is read once per process. Tests can clear the cache
    via ``get_settings.cache_clear()`` to inject fresh values.
    """
    return Settings()
