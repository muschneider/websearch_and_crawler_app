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

    # --- Brave anti-bot / retry ---
    # Total attempts (including the first) before giving up on a 429 / bot-gate.
    brave_retry_attempts: int = Field(default=4, ge=1, le=10)
    # Exponential backoff: delay = min(base * 2**attempt, max) + 0-30% jitter.
    # NOTE: a real Brave 429 typically requires *tens of seconds* to clear at
    # the edge. Aggressive (< 5s) retries usually just burn another attempt.
    brave_retry_backoff_base_ms: int = Field(default=10_000, ge=0, le=600_000)
    brave_retry_backoff_max_ms: int = Field(default=60_000, ge=0, le=600_000)
    # Random pre-navigation pause so requests don't arrive on the same wall-clock
    # tick. Drawn uniformly from [min, max]; set both to 0 to disable.
    brave_prenav_jitter_min_ms: int = Field(default=400, ge=0, le=30_000)
    brave_prenav_jitter_max_ms: int = Field(default=1_800, ge=0, le=30_000)
    # When True, every search starts at the homepage and submits the query
    # through the real search form (mimics a human). Costs ~1 extra navigation
    # on a cold cache. Subsequent requests with the same persona reuse cookies.
    brave_use_homepage_flow: bool = True
    # Per-keystroke delay range (ms) when typing the query into the search box.
    brave_keystroke_min_ms: int = Field(default=60, ge=0, le=1_000)
    brave_keystroke_max_ms: int = Field(default=180, ge=0, le=1_000)
    # Optional outbound proxy used only by the Brave provider. Format:
    # "http://host:port" or "http://user:pass@host:port" or "socks5://...".
    # The single most effective fix when your origin IP is flagged.
    brave_proxy: str | None = None

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

    @field_validator("brave_retry_backoff_max_ms")
    @classmethod
    def _backoff_max_gte_base(cls, value: int, info) -> int:
        base = info.data.get("brave_retry_backoff_base_ms", 0)
        if value < base:
            raise ValueError(
                f"brave_retry_backoff_max_ms must be >= brave_retry_backoff_base_ms "
                f"(got {value} < {base})"
            )
        return value

    @field_validator("brave_prenav_jitter_max_ms")
    @classmethod
    def _jitter_max_gte_min(cls, value: int, info) -> int:
        lo = info.data.get("brave_prenav_jitter_min_ms", 0)
        if value < lo:
            raise ValueError(
                f"brave_prenav_jitter_max_ms must be >= brave_prenav_jitter_min_ms "
                f"(got {value} < {lo})"
            )
        return value

    @field_validator("brave_keystroke_max_ms")
    @classmethod
    def _keystroke_max_gte_min(cls, value: int, info) -> int:
        lo = info.data.get("brave_keystroke_min_ms", 0)
        if value < lo:
            raise ValueError(
                f"brave_keystroke_max_ms must be >= brave_keystroke_min_ms (got {value} < {lo})"
            )
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton ``Settings`` instance.

    Cached so that environment is read once per process. Tests can clear the cache
    via ``get_settings.cache_clear()`` to inject fresh values.
    """
    return Settings()
