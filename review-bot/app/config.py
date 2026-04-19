from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    project_root: Path
    database_url: str
    platform_base_url: str
    engine_base_url: str
    batch_size: int
    provider_name: str
    fallback_provider_name: str
    openai_model: str
    openai_timeout_seconds: float
    openai_max_retries: int
    redis_url: str
    queue_name: str


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    project_root = Path(__file__).resolve().parents[1]
    return Settings(
        project_root=project_root,
        database_url=os.getenv("BOT_DATABASE_URL", f"sqlite:///{project_root / 'bot.db'}"),
        platform_base_url=os.getenv("PLATFORM_BASE_URL", "http://127.0.0.1:18080"),
        engine_base_url=os.getenv("ENGINE_BASE_URL", "http://127.0.0.1:18082"),
        batch_size=int(os.getenv("BOT_BATCH_SIZE", "5")),
        provider_name=os.getenv("BOT_PROVIDER", "stub"),
        fallback_provider_name=os.getenv("BOT_FALLBACK_PROVIDER", "stub"),
        openai_model=os.getenv("BOT_OPENAI_MODEL", "gpt-5.2"),
        openai_timeout_seconds=float(os.getenv("BOT_OPENAI_TIMEOUT_SECONDS", "10")),
        openai_max_retries=int(os.getenv("BOT_OPENAI_MAX_RETRIES", "0")),
        redis_url=os.getenv("BOT_REDIS_URL", "redis://127.0.0.1:6379/0"),
        queue_name=os.getenv("BOT_QUEUE_NAME", "review-bot"),
    )
