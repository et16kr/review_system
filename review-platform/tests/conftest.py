from __future__ import annotations

import faulthandler
import os
import sys
import threading
from pathlib import Path

import pytest


_TESTCLIENT_TIMEOUT_SECONDS = int(os.getenv("REVIEW_PLATFORM_TESTCLIENT_TIMEOUT_SECONDS", "20"))
_TESTCLIENT_BACKED_FILES = {"test_health.py", "test_pr_flow.py"}


@pytest.fixture(autouse=True)
def _bound_review_platform_testclient_gate(request: pytest.FixtureRequest):
    if Path(str(request.node.path)).name not in _TESTCLIENT_BACKED_FILES:
        yield
        return
    if _TESTCLIENT_TIMEOUT_SECONDS <= 0:
        yield
        return

    nodeid = request.node.nodeid
    finished = threading.Event()

    def _watchdog() -> None:
        if finished.wait(_TESTCLIENT_TIMEOUT_SECONDS):
            return
        print(
            f"\n[review-platform-testclient-timeout] {nodeid} exceeded "
            f"{_TESTCLIENT_TIMEOUT_SECONDS}s; dumping all thread stacks.",
            file=sys.stderr,
            flush=True,
        )
        faulthandler.dump_traceback(file=sys.stderr, all_threads=True)
        print(
            "[review-platform-testclient-timeout] Exiting pytest with status 124 after "
            "review-platform FastAPI/TestClient hang.",
            file=sys.stderr,
            flush=True,
        )
        os._exit(124)

    watchdog = threading.Thread(
        target=_watchdog,
        name=f"review-platform-testclient-timeout:{nodeid}",
        daemon=True,
    )
    watchdog.start()
    try:
        yield
    finally:
        finished.set()
        watchdog.join(timeout=0.1)
