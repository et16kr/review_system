from __future__ import annotations

import logging
import time
from enum import Enum
from typing import Any

import httpx

from review_bot.errors import ReviewBotError

logger = logging.getLogger(__name__)

_CIRCUIT_FAILURE_THRESHOLD = 5   # 연속 실패 횟수
_CIRCUIT_RECOVERY_TIMEOUT = 60   # 초 — OPEN 후 HALF_OPEN 진입까지 대기


class _CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class _CircuitBreaker:
    def __init__(self) -> None:
        self._state = _CircuitState.CLOSED
        self._failures = 0
        self._opened_at: float | None = None

    def allow_request(self) -> bool:
        if self._state == _CircuitState.CLOSED:
            return True
        if self._state == _CircuitState.OPEN:
            if time.monotonic() - (self._opened_at or 0) >= _CIRCUIT_RECOVERY_TIMEOUT:
                self._state = _CircuitState.HALF_OPEN
                logger.info("circuit_breaker engine → HALF_OPEN")
                return True
            return False
        # HALF_OPEN: 요청 하나 허용
        return True

    def record_success(self) -> None:
        if self._state != _CircuitState.CLOSED:
            logger.info("circuit_breaker engine → CLOSED")
        self._state = _CircuitState.CLOSED
        self._failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        self._failures += 1
        if self._state == _CircuitState.HALF_OPEN or self._failures >= _CIRCUIT_FAILURE_THRESHOLD:
            self._state = _CircuitState.OPEN
            self._opened_at = time.monotonic()
            logger.warning(
                "circuit_breaker engine → OPEN failures=%d", self._failures
            )

    @property
    def state(self) -> str:
        return self._state.value


_engine_circuit = _CircuitBreaker()


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

    def review_diff(
        self,
        diff: str,
        top_k: int = 8,
        *,
        file_path: str | None = None,
        file_context: str | None = None,
        language_id: str | None = None,
        profile_id: str | None = None,
        context_id: str | None = None,
        dialect_id: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"diff": diff, "top_k": top_k}
        if file_path:
            payload["file_path"] = file_path
        if file_context:
            payload["file_context"] = file_context[:4000]
        if language_id:
            payload["language_id"] = language_id
        if profile_id:
            payload["profile_id"] = profile_id
        if context_id:
            payload["context_id"] = context_id
        if dialect_id:
            payload["dialect_id"] = dialect_id
        if not _engine_circuit.allow_request():
            raise ReviewBotError(
                "review-engine circuit breaker is OPEN — skipping request",
                category="engine_circuit_open",
                retryable=False,
            )

        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = httpx.post(
                    f"{self.base_url}/review/diff",
                    json=payload,
                    timeout=self.timeout_seconds,
                )
                response.raise_for_status()
                _engine_circuit.record_success()
                return response.json()
            except httpx.TimeoutException:
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
                _engine_circuit.record_failure()
                raise last_error
            time.sleep(self.retry_backoff_seconds * (attempt + 1))
        raise RuntimeError("unreachable")

    def search_codebase(
        self,
        query: str,
        top_k: int = 3,
        *,
        project_ref: str | None = None,
    ) -> list[dict[str, Any]]:
        """유사 코드 패턴을 저장소 인덱스에서 검색한다."""
        try:
            payload: dict[str, Any] = {"query": query, "top_k": top_k}
            if project_ref:
                payload["project_ref"] = project_ref
            response = httpx.post(
                f"{self.base_url}/codebase/search",
                json=payload,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            return response.json().get("results", [])
        except Exception:
            return []
