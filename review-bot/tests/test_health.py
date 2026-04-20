from __future__ import annotations

from fastapi.testclient import TestClient

from review_bot.api.main import app


def test_health() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] in {"ok", "degraded"}
    assert "redis" in data
    assert data["redis"] in {"ok", "error"}
