"""Deterministic ASGI client for review-platform tests.

The installed Starlette/AnyIO TestClient path can block in the thread bridge before
app code runs. These tests exercise local harness contracts, so sync endpoints run
inline and requests go through httpx ASGITransport instead of the blocking bridge.
"""

from __future__ import annotations

from typing import Any

import anyio
import anyio.to_thread
import fastapi.dependencies.utils
import fastapi.routing
import httpx
import starlette.concurrency
import starlette.routing


async def _inline_run_in_threadpool(func, *args, **kwargs):
    return func(*args, **kwargs)


async def _inline_to_thread_run_sync(
    func,
    *args,
    abandon_on_cancel: bool = False,
    cancellable: bool | None = None,
    limiter: object | None = None,
):
    del abandon_on_cancel, cancellable, limiter
    return func(*args)


def _install_inline_threadpool() -> None:
    anyio.to_thread.run_sync = _inline_to_thread_run_sync
    fastapi.dependencies.utils.run_in_threadpool = _inline_run_in_threadpool
    fastapi.routing.run_in_threadpool = _inline_run_in_threadpool
    starlette.concurrency.run_in_threadpool = _inline_run_in_threadpool
    starlette.routing.run_in_threadpool = _inline_run_in_threadpool


class TestClient:
    __test__ = False

    def __init__(
        self,
        app,
        base_url: str = "http://testserver",
        raise_server_exceptions: bool = True,
        **_: Any,
    ) -> None:
        self.app = app
        self.base_url = base_url
        self.raise_server_exceptions = raise_server_exceptions

    def __enter__(self):
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def close(self) -> None:
        return None

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("POST", url, **kwargs)

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        return anyio.run(self._request, method, url, kwargs)

    async def _request(self, method: str, url: str, kwargs: dict[str, Any]) -> httpx.Response:
        _install_inline_threadpool()
        transport = httpx.ASGITransport(
            app=self.app,
            raise_app_exceptions=self.raise_server_exceptions,
        )
        async with httpx.AsyncClient(transport=transport, base_url=self.base_url) as client:
            return await client.request(method, url, **kwargs)


_install_inline_threadpool()
