from __future__ import annotations

from typing import Any

import httpx


class EngineClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def review_diff(self, diff: str, top_k: int = 8) -> dict[str, Any]:
        response = httpx.post(
            f"{self.base_url}/review/diff",
            json={"diff": diff, "top_k": top_k},
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()
