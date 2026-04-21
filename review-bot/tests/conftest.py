from __future__ import annotations

import os
import tempfile
from pathlib import Path


def _worker_scoped_test_database_url() -> str:
    worker = os.getenv("PYTEST_XDIST_WORKER", "gw0")
    db_dir = Path(tempfile.gettempdir()) / "review-bot-pytest"
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = db_dir / f"bot-tests-{worker}-{os.getpid()}.db"
    return f"sqlite:///{db_path}"


os.environ["BOT_DATABASE_URL"] = _worker_scoped_test_database_url()
