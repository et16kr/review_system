from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api.main import app
from app.db.models import ReviewRun
from app.db.session import Base, SessionLocal, engine


def test_review_endpoint_enqueues_job_and_persists_run() -> None:
    _reset_db()
    fake_queue = SimpleNamespace(
        name="test-review-bot",
        enqueue=lambda *args, **kwargs: SimpleNamespace(id="job-123"),
    )
    with patch("app.api.main.queue", fake_queue):
        with TestClient(app) as client:
            response = client.post("/internal/review/pr-updated", json={"pr_id": 77})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "queued"
    assert payload["queue_name"] == "test-review-bot"

    session = SessionLocal()
    try:
        run = session.query(ReviewRun).filter(ReviewRun.pr_id == 77).one()
        assert run.status == "queued"
        assert run.job_id == "job-123"
    finally:
        session.close()


def test_next_batch_endpoint_enqueues_job() -> None:
    _reset_db()
    session = SessionLocal()
    try:
        session.add(ReviewRun(pr_id=88, trigger="manual", status="success", head_sha="abc"))
        session.commit()
    finally:
        session.close()

    fake_queue = SimpleNamespace(
        name="test-review-bot",
        enqueue=lambda *args, **kwargs: SimpleNamespace(id="job-456"),
    )
    with patch("app.api.main.queue", fake_queue):
        with TestClient(app) as client:
            response = client.post("/internal/review/next-batch", json={"pr_id": 88})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "queued"
    assert payload["queue_name"] == "test-review-bot"


def test_gitlab_merge_request_webhook_enqueues_job() -> None:
    _reset_db()
    fake_queue = SimpleNamespace(
        name="test-review-bot",
        enqueue=lambda *args, **kwargs: SimpleNamespace(id="job-789"),
    )
    payload = {
        "object_kind": "merge_request",
        "object_attributes": {
            "iid": 91,
            "action": "update",
            "oldrev": "abc123",
        },
    }
    with patch("app.api.main.queue", fake_queue):
        with TestClient(app) as client:
            response = client.post(
                "/webhooks/gitlab/merge-request",
                json=payload,
                headers={"X-Gitlab-Event": "Merge Request Hook"},
            )

    assert response.status_code == 200
    body = response.json()
    assert body["accepted"] is True
    assert body["action"] == "update"
    assert body["status"] == "queued"

    session = SessionLocal()
    try:
        run = session.query(ReviewRun).filter(ReviewRun.pr_id == 91).one()
        assert run.trigger == "gitlab:update"
        assert run.status == "queued"
        assert run.job_id == "job-789"
    finally:
        session.close()


def test_gitlab_merge_request_webhook_ignores_unsupported_action() -> None:
    _reset_db()
    payload = {
        "object_kind": "merge_request",
        "object_attributes": {
            "iid": 92,
            "action": "merge",
        },
    }
    with TestClient(app) as client:
        response = client.post(
            "/webhooks/gitlab/merge-request",
            json=payload,
            headers={"X-Gitlab-Event": "Merge Request Hook"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["accepted"] is False
    assert body["status"] == "ignored"
    assert body["ignored_reason"] == "unsupported_merge_request_action"


def test_gitlab_merge_request_webhook_ignores_update_without_new_commits() -> None:
    _reset_db()
    payload = {
        "object_kind": "merge_request",
        "object_attributes": {
            "iid": 94,
            "action": "update",
        },
    }
    with TestClient(app) as client:
        response = client.post(
            "/webhooks/gitlab/merge-request",
            json=payload,
            headers={"X-Gitlab-Event": "Merge Request Hook"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["accepted"] is False
    assert body["status"] == "ignored"
    assert body["ignored_reason"] == "merge_request_update_without_new_commits"


def test_gitlab_merge_request_webhook_rejects_invalid_secret() -> None:
    _reset_db()
    payload = {
        "object_kind": "merge_request",
        "object_attributes": {
            "iid": 93,
            "action": "open",
        },
    }
    with patch("app.api.main.settings", SimpleNamespace(gitlab_webhook_secret="expected")):
        with TestClient(app) as client:
            response = client.post(
                "/webhooks/gitlab/merge-request",
                json=payload,
                headers={"X-Gitlab-Event": "Merge Request Hook", "X-Gitlab-Token": "wrong"},
            )

    assert response.status_code == 403


def _reset_db() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
