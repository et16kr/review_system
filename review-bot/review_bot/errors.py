from __future__ import annotations

from typing import Any


class ReviewBotError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        category: str,
        retryable: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.retryable = retryable
        self.metadata = dict(metadata or {})
