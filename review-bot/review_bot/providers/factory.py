from __future__ import annotations

from review_bot.config import SUPPORTED_PROVIDER_NAMES, get_settings
from review_bot.providers.base import ReviewCommentProvider
from review_bot.providers.fallback_provider import FallbackReviewCommentProvider
from review_bot.providers.openai_provider import OpenAIReviewCommentProvider
from review_bot.providers.stub_provider import StubReviewCommentProvider


def _build_provider(name: str) -> ReviewCommentProvider:
    if name == "openai":
        return OpenAIReviewCommentProvider()
    if name == "stub":
        return StubReviewCommentProvider()
    supported = ", ".join(sorted(SUPPORTED_PROVIDER_NAMES))
    raise ValueError(f"Unsupported provider: {name}. Supported providers: {supported}")


def build_review_comment_provider() -> ReviewCommentProvider:
    settings = get_settings()
    primary = _build_provider(settings.provider_name)
    if settings.provider_name == settings.fallback_provider_name:
        return primary
    fallback = _build_provider(settings.fallback_provider_name)
    return FallbackReviewCommentProvider(primary=primary, fallback=fallback)
