from __future__ import annotations

from typing import Any
import time

import httpx

from review_bot.errors import ReviewBotError


class EngineClient:
    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float = 30.0,
        max_retries: int = 0,
        retry_backoff_seconds: float = 0.5,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds

    def review_diff(self, diff: str, top_k: int = 8) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = httpx.post(
                    f"{self.base_url}/review/diff",
                    json={"diff": diff, "top_k": top_k},
                    timeout=self.timeout_seconds,
                )
                response.raise_for_status()
                return response.json()
            except httpx.TimeoutException as exc:
                last_error = ReviewBotError(
                    "Timed out while calling review-engine /review/diff",
                    category="engine_timeout",
                    retryable=True,
                )
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                retryable = status_code >= 500
                last_error = ReviewBotError(
                    f"review-engine returned {status_code}: {exc.response.text[:300]}",
                    category="engine_api",
                    retryable=retryable,
                )
            except httpx.HTTPError as exc:
                last_error = ReviewBotError(
                    f"review-engine request failed: {exc}",
                    category="engine_transport",
                    retryable=True,
                )
            if attempt >= self.max_retries:
                assert last_error is not None
                raise last_error
            time.sleep(self.retry_backoff_seconds * (attempt + 1))
        raise RuntimeError("unreachable")
