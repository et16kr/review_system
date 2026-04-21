from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    project_root: Path
    database_url: str
    review_system_adapter_name: str
    review_system_base_url: str
    engine_base_url: str
    engine_timeout_seconds: float
    engine_max_retries: int
    engine_retry_backoff_seconds: float
    batch_size: int
    provider_name: str
    fallback_provider_name: str
    openai_model: str
    openai_timeout_seconds: float
    openai_max_retries: int
    gitlab_token: str | None
    gitlab_webhook_secret: str | None
    redis_url: str
    queue_detect_name: str
    queue_publish_name: str
    queue_sync_name: str
    minimum_publish_score: float
    gitlab_api_timeout_seconds: float
    gitlab_api_max_retries: int
    gitlab_api_retry_backoff_seconds: float
    feedback_resolved_penalty: float
    feedback_reply_penalty: float
    feedback_reply_suppression_threshold: int
    rule_family_cap: int
    dead_letter_enabled: bool
    policy_path: str | None
    legacy_review_system: str
    legacy_project_ref: str
    bot_author_name: str
    repeat_open_thread_reminder_enabled: bool
    resolved_unchanged_resurface_enabled: bool
    verify_enabled: bool
    verify_confidence_threshold: float
    verify_score_band: float


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    project_root = Path(__file__).resolve().parents[1]
    return Settings(
        project_root=project_root,
        database_url=os.getenv("BOT_DATABASE_URL", f"sqlite:///{project_root / 'bot.db'}"),
        review_system_adapter_name=os.getenv("REVIEW_SYSTEM_ADAPTER", "local_platform"),
        review_system_base_url=os.getenv(
            "REVIEW_SYSTEM_BASE_URL",
            os.getenv("PLATFORM_BASE_URL", "http://127.0.0.1:18080"),
        ),
        engine_base_url=os.getenv("ENGINE_BASE_URL", "http://127.0.0.1:18082"),
        engine_timeout_seconds=float(os.getenv("BOT_ENGINE_TIMEOUT_SECONDS", "30")),
        engine_max_retries=int(os.getenv("BOT_ENGINE_MAX_RETRIES", "2")),
        engine_retry_backoff_seconds=float(os.getenv("BOT_ENGINE_RETRY_BACKOFF_SECONDS", "0.5")),
        batch_size=int(os.getenv("BOT_BATCH_SIZE", "10")),
        provider_name=os.getenv("BOT_PROVIDER", "openai"),
        fallback_provider_name=os.getenv("BOT_FALLBACK_PROVIDER", "stub"),
        openai_model=os.getenv("BOT_OPENAI_MODEL", "gpt-4o"),
        openai_timeout_seconds=float(os.getenv("BOT_OPENAI_TIMEOUT_SECONDS", "30")),
        openai_max_retries=int(os.getenv("BOT_OPENAI_MAX_RETRIES", "2")),
        gitlab_token=os.getenv("GITLAB_TOKEN"),
        gitlab_webhook_secret=os.getenv("GITLAB_WEBHOOK_SECRET"),
        redis_url=os.getenv("BOT_REDIS_URL", "redis://127.0.0.1:6379/0"),
        queue_detect_name=os.getenv("BOT_QUEUE_DETECT_NAME", "review-detect"),
        queue_publish_name=os.getenv("BOT_QUEUE_PUBLISH_NAME", "review-publish"),
        queue_sync_name=os.getenv("BOT_QUEUE_SYNC_NAME", "review-sync"),
        minimum_publish_score=float(os.getenv("BOT_MINIMUM_PUBLISH_SCORE", "0.65")),
        gitlab_api_timeout_seconds=float(os.getenv("BOT_GITLAB_API_TIMEOUT_SECONDS", "30")),
        gitlab_api_max_retries=int(os.getenv("BOT_GITLAB_API_MAX_RETRIES", "2")),
        gitlab_api_retry_backoff_seconds=float(
            os.getenv("BOT_GITLAB_API_RETRY_BACKOFF_SECONDS", "0.5")
        ),
        feedback_resolved_penalty=float(os.getenv("BOT_FEEDBACK_RESOLVED_PENALTY", "0.08")),
        feedback_reply_penalty=float(os.getenv("BOT_FEEDBACK_REPLY_PENALTY", "0.05")),
        feedback_reply_suppression_threshold=int(
            os.getenv("BOT_FEEDBACK_REPLY_SUPPRESSION_THRESHOLD", "2")
        ),
        rule_family_cap=int(os.getenv("BOT_RULE_FAMILY_CAP", "2")),
        dead_letter_enabled=os.getenv("BOT_DEAD_LETTER_ENABLED", "1") not in {"0", "false", "False"},
        policy_path=os.getenv("BOT_POLICY_PATH"),
        legacy_review_system=os.getenv("BOT_LEGACY_REVIEW_SYSTEM", "legacy"),
        legacy_project_ref=os.getenv("BOT_LEGACY_PROJECT_REF", "legacy/default"),
        bot_author_name=os.getenv("BOT_AUTHOR_NAME", "review-bot"),
        repeat_open_thread_reminder_enabled=os.getenv(
            "BOT_REPEAT_OPEN_THREAD_REMINDER_ENABLED", "0"
        ) not in {"0", "false", "False"},
        resolved_unchanged_resurface_enabled=os.getenv(
            "BOT_RESOLVED_UNCHANGED_RESURFACE_ENABLED", "0"
        ) not in {"0", "false", "False"},
        verify_enabled=os.getenv("BOT_VERIFY_ENABLED", "0") not in {"0", "false", "False"},
        verify_confidence_threshold=float(
            os.getenv("BOT_VERIFY_CONFIDENCE_THRESHOLD", "0.85")
        ),
        verify_score_band=float(os.getenv("BOT_VERIFY_SCORE_BAND", "0.10")),
    )
