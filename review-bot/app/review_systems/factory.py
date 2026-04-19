from __future__ import annotations

from app.config import get_settings
from app.review_systems.base import ReviewSystemAdapter
from app.review_systems.gitlab import GitLabReviewSystemAdapter
from app.review_systems.local_platform import LocalPlatformReviewSystemAdapter


def build_review_system_adapter() -> ReviewSystemAdapter:
    settings = get_settings()
    if settings.review_system_adapter_name == "gitlab":
        if not settings.gitlab_token:
            raise ValueError("GITLAB_TOKEN is required when REVIEW_SYSTEM_ADAPTER=gitlab")
        return GitLabReviewSystemAdapter(
            base_url=settings.review_system_base_url,
            token=settings.gitlab_token,
            project_id=settings.gitlab_project_id,
        )
    return LocalPlatformReviewSystemAdapter(settings.review_system_base_url)
