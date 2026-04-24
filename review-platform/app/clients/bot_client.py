from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx


class UnsupportedBotControlError(RuntimeError):
    pass


class BotClient:
    def __init__(
        self,
        base_url: str,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._transport = transport

    def trigger_review(
        self,
        key: dict[str, str],
        *,
        trigger: str = "manual",
        mode: str = "full",
        title: str | None = None,
        draft: bool = False,
        source_branch: str | None = None,
        target_branch: str | None = None,
        base_sha: str | None = None,
        start_sha: str | None = None,
        head_sha: str | None = None,
    ) -> dict[str, Any]:
        response = self._post(
            f"{self.base_url}/internal/review/runs",
            json={
                "key": key,
                "trigger": trigger,
                "mode": mode,
                "title": title,
                "draft": draft,
                "source_branch": source_branch,
                "target_branch": target_branch,
                "base_sha": base_sha,
                "start_sha": start_sha,
                "head_sha": head_sha,
            },
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()

    def publish_next_batch(
        self,
        key: dict[str, str],
        reason: str = "manual_next_batch",
    ) -> dict[str, Any]:
        del key, reason
        raise UnsupportedBotControlError(
            "review-bot does not expose a key-based next-batch API."
        )

    def get_state(self, key: dict[str, str]) -> dict[str, Any]:
        response = self._get(
            self._request_state_url(key),
            timeout=10.0,
        )
        response.raise_for_status()
        return response.json()

    def _post(self, url: str, *, json: dict[str, Any], timeout: float) -> httpx.Response:
        with httpx.Client(transport=self._transport) as client:
            return client.post(url, json=json, timeout=timeout)

    def _get(self, url: str, *, timeout: float) -> httpx.Response:
        with httpx.Client(transport=self._transport) as client:
            return client.get(url, timeout=timeout)

    def _request_state_url(self, key: dict[str, str]) -> str:
        review_system = quote(key["review_system"], safe="")
        project_ref = quote(key["project_ref"], safe="/")
        review_request_id = quote(key["review_request_id"], safe="")
        return (
            f"{self.base_url}/internal/review/requests/"
            f"{review_system}/{project_ref}/{review_request_id}"
        )
