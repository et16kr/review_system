from __future__ import annotations

from app.config import get_settings
from app.providers.base import ReviewCommentProvider
from app.providers.fallback_provider import FallbackReviewCommentProvider
from app.providers.openai_provider import OpenAIReviewCommentProvider
from app.providers.stub_provider import StubReviewCommentProvider


def _build_provider(name: str) -> ReviewCommentProvider:
    if name == "openai":
        return OpenAIReviewCommentProvider()
    return StubReviewCommentProvider()


def build_review_comment_provider() -> ReviewCommentProvider:
    settings = get_settings()
    primary = _build_provider(settings.provider_name)
    if settings.provider_name == settings.fallback_provider_name:
        return primary
    fallback = _build_provider(settings.fallback_provider_name)
    return FallbackReviewCommentProvider(primary=primary, fallback=fallback)
