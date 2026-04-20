from __future__ import annotations

from review_bot.config import get_settings
from review_bot.review_systems.base import ReviewSystemAdapterV2
from review_bot.review_systems.gitlab import GitLabReviewSystemAdapter
from review_bot.review_systems.local_platform import LocalPlatformReviewSystemAdapter


def build_review_system_adapter() -> ReviewSystemAdapterV2:
    settings = get_settings()
    if settings.review_system_adapter_name == "gitlab":
        if not settings.gitlab_token:
            raise ValueError("GITLAB_TOKEN is required when REVIEW_SYSTEM_ADAPTER=gitlab")
        return GitLabReviewSystemAdapter(
            base_url=settings.review_system_base_url,
            token=settings.gitlab_token,
            timeout_seconds=settings.gitlab_api_timeout_seconds,
            max_retries=settings.gitlab_api_max_retries,
            retry_backoff_seconds=settings.gitlab_api_retry_backoff_seconds,
        )
    return LocalPlatformReviewSystemAdapter(settings.review_system_base_url)
