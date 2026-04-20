from __future__ import annotations

import httpx
import pytest

from review_bot.clients.engine_client import EngineClient, _CircuitState, _engine_circuit
from review_bot.errors import ReviewBotError


def _reset_circuit() -> None:
    _engine_circuit._state = _CircuitState.CLOSED
    _engine_circuit._failures = 0
    _engine_circuit._opened_at = None


def test_engine_client_retries_timeout_and_then_succeeds(monkeypatch) -> None:
    _reset_circuit()
    client = EngineClient(
        "http://review-engine.local",
        timeout_seconds=1.0,
        max_retries=1,
        retry_backoff_seconds=0.0,
    )
    calls = {"count": 0}

    def fake_post(url: str, *, json=None, timeout=None):
        del json, timeout
        calls["count"] += 1
        if calls["count"] == 1:
            raise httpx.ReadTimeout("timeout", request=httpx.Request("POST", url))
        return httpx.Response(
            200,
            json={"detected_patterns": [], "results": []},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    payload = client.review_diff("@@ -1 +1 @@\n-old\n+new\n")

    assert payload["results"] == []
    assert calls["count"] == 2


def test_engine_client_raises_structured_error_after_retries(monkeypatch) -> None:
    _reset_circuit()
    client = EngineClient(
        "http://review-engine.local",
        timeout_seconds=1.0,
        max_retries=1,
        retry_backoff_seconds=0.0,
    )

    def fake_post(url: str, *, json=None, timeout=None):
        del json, timeout
        raise httpx.ConnectError("boom", request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)

    try:
        client.review_diff("@@ -1 +1 @@\n-old\n+new\n")
    except ReviewBotError as exc:
        assert exc.category == "engine_transport"
        assert exc.retryable is True
    else:
        raise AssertionError("Expected ReviewBotError")


def test_engine_client_counts_failures_per_request_not_per_retry_attempt(monkeypatch) -> None:
    _reset_circuit()
    client = EngineClient(
        "http://review-engine.local",
        timeout_seconds=1.0,
        max_retries=2,
        retry_backoff_seconds=0.0,
    )
    calls = {"count": 0}

    def fake_post(url: str, *, json=None, timeout=None):
        del json, timeout
        calls["count"] += 1
        raise httpx.ConnectError("boom", request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)

    with pytest.raises(ReviewBotError):
        client.review_diff("@@ -1 +1 @@\n-old\n+new\n")

    assert calls["count"] == 3
    assert _engine_circuit._failures == 1
    assert _engine_circuit.state == "closed"
