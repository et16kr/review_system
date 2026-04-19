from __future__ import annotations

from typing import Any

import httpx


class BotClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def trigger_review(self, pr_id: int, trigger: str = "manual") -> dict[str, Any]:
        response = httpx.post(
            f"{self.base_url}/internal/review/pr-updated",
            json={"pr_id": pr_id, "trigger": trigger},
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()

    def publish_next_batch(self, pr_id: int, reason: str = "manual_next_batch") -> dict[str, Any]:
        response = httpx.post(
            f"{self.base_url}/internal/review/next-batch",
            json={"pr_id": pr_id, "reason": reason},
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()

    def get_state(self, pr_id: int) -> dict[str, Any]:
        response = httpx.get(
            f"{self.base_url}/internal/review/state/{pr_id}",
            timeout=10.0,
        )
        response.raise_for_status()
        return response.json()
