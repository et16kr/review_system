from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    project_root: Path
    storage_root: Path
    database_url: str
    bot_base_url: str
    public_base_url: str
    clone_base_url: str | None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    project_root = Path(__file__).resolve().parents[1]
    storage_root = Path(os.getenv("PLATFORM_STORAGE_ROOT", project_root / "storage" / "repos"))
    database_url = os.getenv("PLATFORM_DATABASE_URL", f"sqlite:///{project_root / 'platform.db'}")
    public_base_url = os.getenv("PLATFORM_PUBLIC_BASE_URL", "http://127.0.0.1:18080")
    return Settings(
        project_root=project_root,
        storage_root=storage_root,
        database_url=database_url,
        bot_base_url=os.getenv("PLATFORM_BOT_BASE_URL", "http://127.0.0.1:18081"),
        public_base_url=public_base_url.rstrip("/"),
        clone_base_url=os.getenv("PLATFORM_CLONE_BASE_URL"),
    )
