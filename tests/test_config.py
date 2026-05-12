"""Tests for environment-driven configuration."""

from __future__ import annotations

import os

import pytest
from pydantic import ValidationError

from websearch_api.config import Settings, get_settings


def test_defaults_are_sane(monkeypatch: pytest.MonkeyPatch) -> None:
    # Strip any WEBSEARCH_* env vars inherited from the parent shell so we
    # actually exercise the in-code defaults.
    for key in list(os.environ):
        if key.startswith("WEBSEARCH_"):
            monkeypatch.delenv(key, raising=False)

    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.host == "0.0.0.0"
    assert s.port == 8000
    assert s.browser_headless is True
    assert s.default_max_results <= s.max_results_hard_cap
    assert s.cors_origins == ["*"]


def test_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WEBSEARCH_PORT", "9001")
    monkeypatch.setenv("WEBSEARCH_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("WEBSEARCH_CORS_ORIGINS", "http://a.test, http://b.test")
    monkeypatch.setenv("WEBSEARCH_BROWSER_HEADLESS", "false")

    get_settings.cache_clear()
    s = get_settings()
    assert s.port == 9001
    assert s.log_level == "DEBUG"
    assert s.cors_origins == ["http://a.test", "http://b.test"]
    assert s.browser_headless is False


def test_invalid_log_level_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WEBSEARCH_LOG_LEVEL", "NOPE")
    get_settings.cache_clear()
    with pytest.raises(ValidationError):
        get_settings()


def test_hard_cap_must_be_ge_default() -> None:
    with pytest.raises(ValidationError):
        Settings(default_max_results=20, max_results_hard_cap=10, _env_file=None)  # type: ignore[call-arg]
