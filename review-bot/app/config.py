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
    batch_size: int
    provider_name: str
    fallback_provider_name: str
    openai_model: str
    openai_timeout_seconds: float
    openai_max_retries: int
    gitlab_token: str | None
    gitlab_project_id: str | None
    gitlab_webhook_secret: str | None
    redis_url: str
    queue_name: str
    minimum_publish_score: float


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
        batch_size=int(os.getenv("BOT_BATCH_SIZE", "5")),
        provider_name=os.getenv("BOT_PROVIDER", "stub"),
        fallback_provider_name=os.getenv("BOT_FALLBACK_PROVIDER", "stub"),
        openai_model=os.getenv("BOT_OPENAI_MODEL", "gpt-5.2"),
        openai_timeout_seconds=float(os.getenv("BOT_OPENAI_TIMEOUT_SECONDS", "10")),
        openai_max_retries=int(os.getenv("BOT_OPENAI_MAX_RETRIES", "0")),
        gitlab_token=os.getenv("GITLAB_TOKEN"),
        gitlab_project_id=os.getenv("GITLAB_PROJECT_ID"),
        gitlab_webhook_secret=os.getenv("GITLAB_WEBHOOK_SECRET"),
        redis_url=os.getenv("BOT_REDIS_URL", "redis://127.0.0.1:6379/0"),
        queue_name=os.getenv("BOT_QUEUE_NAME", "review-bot"),
        minimum_publish_score=float(os.getenv("BOT_MINIMUM_PUBLISH_SCORE", "0.65")),
    )
