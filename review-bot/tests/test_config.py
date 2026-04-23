from __future__ import annotations

import pytest

from review_bot.config import get_settings
from review_bot.providers.factory import _build_provider


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    try:
        yield
    finally:
        get_settings.cache_clear()


def test_get_settings_accepts_supported_provider_names(monkeypatch) -> None:
    monkeypatch.setenv("BOT_PROVIDER", " OPENAI ")
    monkeypatch.setenv("BOT_FALLBACK_PROVIDER", "stub")

    settings = get_settings()

    assert settings.provider_name == "openai"
    assert settings.fallback_provider_name == "stub"


def test_get_settings_rejects_unknown_primary_provider(monkeypatch) -> None:
    monkeypatch.setenv("BOT_PROVIDER", "openia")

    with pytest.raises(ValueError, match="BOT_PROVIDER must be one of: openai, stub"):
        get_settings()


def test_get_settings_rejects_unknown_fallback_provider(monkeypatch) -> None:
    monkeypatch.setenv("BOT_PROVIDER", "openai")
    monkeypatch.setenv("BOT_FALLBACK_PROVIDER", "local")

    with pytest.raises(
        ValueError,
        match="BOT_FALLBACK_PROVIDER must be one of: openai, stub",
    ):
        get_settings()


def test_provider_factory_rejects_unknown_provider_name() -> None:
    with pytest.raises(ValueError, match="Unsupported provider: local"):
        _build_provider("local")
