from __future__ import annotations

import faulthandler
import os
import sys
import tempfile
import threading
from pathlib import Path

import pytest


_API_QUEUE_TIMEOUT_SECONDS = int(os.getenv("REVIEW_BOT_API_QUEUE_TEST_TIMEOUT_SECONDS", "45"))


def _worker_scoped_test_database_url() -> str:
    worker = os.getenv("PYTEST_XDIST_WORKER", "gw0")
    db_dir = Path(tempfile.gettempdir()) / "review-bot-pytest"
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = db_dir / f"bot-tests-{worker}-{os.getpid()}.db"
    return f"sqlite:///{db_path}"


os.environ["BOT_DATABASE_URL"] = _worker_scoped_test_database_url()
os.environ.pop("GITLAB_WEBHOOK_SECRET", None)


@pytest.fixture(autouse=True)
def _bound_api_queue_testclient_gate(request: pytest.FixtureRequest):
    if Path(str(request.node.path)).name != "test_api_queue.py":
        yield
        return
    if _API_QUEUE_TIMEOUT_SECONDS <= 0:
        yield
        return

    nodeid = request.node.nodeid
    finished = threading.Event()

    def _watchdog() -> None:
        if finished.wait(_API_QUEUE_TIMEOUT_SECONDS):
            return
        print(
            f"\n[api-queue-timeout] {nodeid} exceeded "
            f"{_API_QUEUE_TIMEOUT_SECONDS}s; dumping all thread stacks.",
            file=sys.stderr,
            flush=True,
        )
        faulthandler.dump_traceback(file=sys.stderr, all_threads=True)
        print(
            "[api-queue-timeout] Exiting pytest with status 124 after API queue ASGI test hang.",
            file=sys.stderr,
            flush=True,
        )
        os._exit(124)

    watchdog = threading.Thread(
        target=_watchdog,
        name=f"api-queue-timeout:{nodeid}",
        daemon=True,
    )
    watchdog.start()
    try:
        yield
    finally:
        finished.set()
        watchdog.join(timeout=0.1)
