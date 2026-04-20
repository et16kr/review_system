from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from review_bot.api import main as api_main
from review_bot.db.models import ReviewRequest, ReviewRun
from review_bot.db.session import Base, SessionLocal, engine


class FakeQueue:
    def __init__(self, name: str, job_id: str) -> None:
        self.name = name
        self.job_id = job_id
        self.calls: list[tuple[object, tuple[object, ...]]] = []

    def enqueue(self, func, *args, **kwargs):
        del kwargs
        self.calls.append((func, args))
        return type("Job", (), {"id": self.job_id})()


def test_create_review_run_endpoint_enqueues_detect_job_and_persists_run() -> None:
    _reset_db()
    fake_queue = FakeQueue(name="review-detect-test", job_id="job-123")

    with patch.object(api_main, "init_db", lambda: None):
        with patch.object(api_main, "detect_queue", fake_queue):
            with TestClient(api_main.app) as client:
                response = client.post(
                    "/internal/review/runs",
                    json={
                        "key": {
                            "review_system": "gitlab",
                            "project_ref": "root/altidev4-review",
                            "review_request_id": "77",
                        },
                        "trigger": "manual:test",
                        "mode": "full",
                        "title": "TDE review",
                        "head_sha": "abc123",
                    },
                )

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "accepted": True,
        "review_run_id": payload["review_run_id"],
        "status": "queued",
        "queue_name": "review-detect-test",
    }
    assert len(fake_queue.calls) == 1

    session = SessionLocal()
    try:
        review_request = session.query(ReviewRequest).filter_by(review_request_id="77").one()
        run = session.query(ReviewRun).filter_by(id=payload["review_run_id"]).one()
        assert review_request.review_system == "gitlab"
        assert review_request.project_ref == "root/altidev4-review"
        assert run.review_request_pk == review_request.id
        assert run.status == "queued"
        assert run.job_id == "job-123"
        assert run.mode == "full"
    finally:
        session.close()


def test_create_review_run_endpoint_reuses_pending_run_without_reenqueue() -> None:
    _reset_db()
    fake_queue = FakeQueue(name="review-detect-test", job_id="job-234")

    payload = {
        "key": {
            "review_system": "gitlab",
            "project_ref": "root/altidev4-review",
            "review_request_id": "78",
        },
        "trigger": "manual:test",
        "mode": "manual",
        "title": "TDE review",
        "head_sha": "abc123",
    }

    with patch.object(api_main, "init_db", lambda: None):
        with patch.object(api_main, "detect_queue", fake_queue):
            with TestClient(api_main.app) as client:
                first = client.post("/internal/review/runs", json=payload)
                second = client.post("/internal/review/runs", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["review_run_id"] == second.json()["review_run_id"]
    assert first.json()["status"] == "queued"
    assert second.json()["status"] == "queued"
    assert len(fake_queue.calls) == 1


def test_create_review_run_endpoint_returns_actual_status_for_reused_running_run() -> None:
    _reset_db()
    fake_queue = FakeQueue(name="review-detect-test", job_id="job-235")

    payload = {
        "key": {
            "review_system": "gitlab",
            "project_ref": "root/altidev4-review",
            "review_request_id": "79",
        },
        "trigger": "manual:test",
        "mode": "manual",
        "title": "TDE review",
        "head_sha": "abc123",
    }

    with patch.object(api_main, "init_db", lambda: None):
        with patch.object(api_main, "detect_queue", fake_queue):
            with TestClient(api_main.app) as client:
                first = client.post("/internal/review/runs", json=payload)

                session = SessionLocal()
                try:
                    run = session.query(ReviewRun).filter_by(id=first.json()["review_run_id"]).one()
                    run.status = "running"
                    session.commit()
                finally:
                    session.close()

                second = client.post("/internal/review/runs", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["review_run_id"] == second.json()["review_run_id"]
    assert second.json()["status"] == "running"
    assert len(fake_queue.calls) == 1


def test_publish_endpoint_enqueues_publish_job() -> None:
    fake_queue = FakeQueue(name="review-publish-test", job_id="job-456")

    with patch.object(api_main, "init_db", lambda: None):
        with patch.object(api_main, "publish_queue", fake_queue):
            with TestClient(api_main.app) as client:
                response = client.post("/internal/review/runs/run-001/publish")

    assert response.status_code == 200
    assert response.json() == {
        "accepted": True,
        "review_run_id": "run-001",
        "queue_name": "review-publish-test",
        "status": "queued",
    }
    assert len(fake_queue.calls) == 1


def test_gitlab_note_webhook_creates_manual_run_for_bot_mention() -> None:
    _reset_db()
    fake_queue = FakeQueue(name="review-detect-test", job_id="job-789")
    payload = {
        "object_kind": "note",
        "user": {"username": "alice"},
        "project": {"path_with_namespace": "group/project-a"},
        "merge_request": {
            "iid": 91,
            "title": "MR title",
            "source_branch": "feature",
            "target_branch": "main",
            "last_commit": {"id": "head123"},
        },
        "object_attributes": {
            "id": 501,
            "note": "@review-bot review 부탁드립니다.",
            "noteable_type": "MergeRequest",
            "system": False,
        },
    }

    with patch.object(api_main, "init_db", lambda: None):
        with patch.object(api_main, "detect_queue", fake_queue):
            with TestClient(api_main.app) as client:
                response = client.post(
                    "/webhooks/gitlab/merge-request",
                    json=payload,
                    headers={"X-Gitlab-Event": "Note Hook"},
                )

    assert response.status_code == 200
    body = response.json()
    assert body["accepted"] is True
    assert body["event"] == "gitlab_note"
    assert body["action"] == "mention"
    assert body["status"] == "queued"

    session = SessionLocal()
    try:
        run = session.query(ReviewRun).filter_by(id=body["review_run_id"]).one()
        assert run.review_system == "gitlab"
        assert run.project_ref == "group/project-a"
        assert run.review_request_id == "91"
        assert run.trigger == "gitlab:note_mention"
        assert run.mode == "manual"
        assert run.status == "queued"
        assert run.job_id == "job-789"
    finally:
        session.close()


def test_gitlab_note_webhook_reuses_pending_run_without_reenqueue() -> None:
    _reset_db()
    fake_queue = FakeQueue(name="review-detect-test", job_id="job-790")
    payload = {
        "object_kind": "note",
        "user": {"username": "alice"},
        "project": {"path_with_namespace": "group/project-a"},
        "merge_request": {
            "iid": 92,
            "title": "MR title",
            "source_branch": "feature",
            "target_branch": "main",
            "last_commit": {"id": "head123"},
        },
        "object_attributes": {
            "id": 504,
            "note": "@review-bot review 부탁드립니다.",
            "noteable_type": "MergeRequest",
            "system": False,
        },
    }

    with patch.object(api_main, "init_db", lambda: None):
        with patch.object(api_main, "detect_queue", fake_queue):
            with TestClient(api_main.app) as client:
                first = client.post(
                    "/webhooks/gitlab/merge-request",
                    json=payload,
                    headers={"X-Gitlab-Event": "Note Hook"},
                )
                second = client.post(
                    "/webhooks/gitlab/merge-request",
                    json=payload,
                    headers={"X-Gitlab-Event": "Note Hook"},
                )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["review_run_id"] == second.json()["review_run_id"]
    assert first.json()["status"] == "queued"
    assert second.json()["status"] == "queued"
    assert len(fake_queue.calls) == 1


def test_gitlab_note_webhook_ignores_note_without_bot_mention() -> None:
    _reset_db()
    payload = {
        "object_kind": "note",
        "user": {"username": "alice"},
        "project": {"path_with_namespace": "group/project-a"},
        "merge_request": {
            "iid": 94,
        },
        "object_attributes": {
            "id": 502,
            "note": "일반 코멘트입니다.",
            "noteable_type": "MergeRequest",
            "system": False,
        },
    }

    with patch.object(api_main, "init_db", lambda: None):
        with TestClient(api_main.app) as client:
            response = client.post(
                "/webhooks/gitlab/merge-request",
                json=payload,
                headers={"X-Gitlab-Event": "Note Hook"},
            )

    assert response.status_code == 200
    body = response.json()
    assert body["accepted"] is False
    assert body["status"] == "ignored"
    assert body["ignored_reason"] == "missing_review_request_mention:@review-bot"


def test_gitlab_note_webhook_ignores_bot_authored_note() -> None:
    _reset_db()
    payload = {
        "object_kind": "note",
        "user": {"username": "review-bot"},
        "project": {"path_with_namespace": "group/project-a"},
        "merge_request": {
            "iid": 95,
        },
        "object_attributes": {
            "id": 503,
            "note": "@review-bot review 부탁드립니다.",
            "noteable_type": "MergeRequest",
            "system": False,
        },
    }

    with patch.object(api_main, "init_db", lambda: None):
        with TestClient(api_main.app) as client:
            response = client.post(
                "/webhooks/gitlab/merge-request",
                json=payload,
                headers={"X-Gitlab-Event": "Note Hook"},
            )

    assert response.status_code == 200
    body = response.json()
    assert body["accepted"] is False
    assert body["status"] == "ignored"
    assert body["ignored_reason"] == "bot_authored_note"


def test_gitlab_merge_request_webhook_is_ignored_when_manual_mention_is_required() -> None:
    _reset_db()
    payload = {
        "object_kind": "merge_request",
        "project": {"path_with_namespace": "group/project-a"},
        "object_attributes": {
            "iid": 96,
            "action": "update",
            "oldrev": "abc123",
        },
    }

    with patch.object(api_main, "init_db", lambda: None):
        with TestClient(api_main.app) as client:
            response = client.post(
                "/webhooks/gitlab/merge-request",
                json=payload,
                headers={"X-Gitlab-Event": "Merge Request Hook"},
            )

    assert response.status_code == 200
    body = response.json()
    assert body["accepted"] is False
    assert body["status"] == "ignored"
    assert body["ignored_reason"] == "manual_review_requires_bot_mention_comment"


def test_gitlab_note_webhook_tracks_same_iid_per_project_as_distinct_requests() -> None:
    _reset_db()
    fake_queue = FakeQueue(name="review-detect-test", job_id="job-900")

    with patch.object(api_main, "init_db", lambda: None):
        with patch.object(api_main, "detect_queue", fake_queue):
            with TestClient(api_main.app) as client:
                for project_ref in ("group/project-a", "group/project-b"):
                    response = client.post(
                        "/webhooks/gitlab/merge-request",
                        json={
                            "object_kind": "note",
                            "user": {"username": "alice"},
                            "project": {"path_with_namespace": project_ref},
                            "merge_request": {
                                "iid": 7,
                                "title": f"{project_ref} MR",
                            },
                            "object_attributes": {
                                "id": 700,
                                "note": "@review-bot review 부탁드립니다.",
                                "noteable_type": "MergeRequest",
                                "system": False,
                            },
                        },
                        headers={"X-Gitlab-Event": "Note Hook"},
                    )
                    assert response.status_code == 200

    session = SessionLocal()
    try:
        requests = (
            session.query(ReviewRequest)
            .filter_by(review_system="gitlab", review_request_id="7")
            .order_by(ReviewRequest.project_ref.asc())
            .all()
        )
        assert [item.project_ref for item in requests] == [
            "group/project-a",
            "group/project-b",
        ]
    finally:
        session.close()


def _reset_db() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
