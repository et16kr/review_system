from __future__ import annotations

from fastapi.testclient import TestClient

from app.api import main as api_main
from app.ingest.build_records import ingest_all_sources
from app.retrieve.search import GuidelineSearchService


def test_review_code_api_shape(monkeypatch, fixture_settings) -> None:
    ingest_all_sources(fixture_settings)
    monkeypatch.setattr(api_main, "service", GuidelineSearchService(fixture_settings))
    client = TestClient(api_main.app)

    response = client.post(
        "/review/code",
        json={
            "code": "#include <stdio.h>\nvoid bad(){ int* ptr = new int(1); free(ptr); }\n",
            "top_k": 3,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"query_text", "detected_patterns", "results"}
    assert isinstance(payload["results"], list)
    assert {"rule_no", "title", "score"} <= set(payload["results"][0])
