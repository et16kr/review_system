from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from review_engine.api import main as api_main
from review_engine.ingest.build_records import ingest_all_sources
from review_engine.retrieve.search import GuidelineSearchService


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
    assert set(payload) == {
        "language_id",
        "profile_id",
        "prompt_overlay_refs",
        "query_text",
        "detected_patterns",
        "results",
    }
    assert payload["language_id"] == "cpp"
    assert payload["profile_id"] == "default"
    assert payload["prompt_overlay_refs"] == []
    assert isinstance(payload["results"], list)
    assert {
        "rule_no",
        "title",
        "score",
        "source_family",
        "authority",
        "conflict_policy",
        "pack_id",
        "source_kind",
        "priority_tier",
        "pack_weight",
        "language_id",
        "conflict_action",
    } <= set(payload["results"][0])


def test_rule_api_returns_legacy_and_canonical_metadata(monkeypatch, fixture_settings) -> None:
    ingest_all_sources(fixture_settings)
    monkeypatch.setattr(api_main, "service", GuidelineSearchService(fixture_settings))
    client = TestClient(api_main.app)

    response = client.get("/rule/R.10")

    assert response.status_code == 200
    payload = response.json()
    assert payload["rule_no"] == "R.10"
    assert payload["source_family"] == "cpp_core"
    assert payload["authority"] == "external"
    assert payload["conflict_policy"] == "authoritative"
    assert payload["pack_id"] == "cpp_core"
    assert payload["source_kind"] == "public_standard"
    assert payload["priority_tier"] == "override"
    assert payload["language_id"] == "cpp"
    assert payload["conflict_action"] == "compatible"


def test_codebase_index_rejects_root_outside_allowed_roots(tmp_path: Path) -> None:
    client = TestClient(api_main.app)

    response = client.post("/codebase/index", json={"root_path": str(tmp_path)})

    assert response.status_code == 403
    assert "allowed roots" in response.json()["detail"]


def test_codebase_index_accepts_configured_allowed_root(monkeypatch, tmp_path: Path) -> None:
    indexed_chunks: list[list[dict[str, object]]] = []

    class FakeStore:
        def clear(self) -> None:
            return None

        def upsert_chunks(self, chunks: list[dict[str, object]]) -> int:
            indexed_chunks.append(chunks)
            return len(chunks)

    source_dir = tmp_path / "repo"
    source_dir.mkdir()
    (source_dir / "sample.cpp").write_text(
        "void sampleFunction() {\n"
        "    int counter = 0;\n"
        "    counter += 1;\n"
        "    counter += 2;\n"
        "    if (counter > 0) {\n"
        "        counter += 3;\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("REVIEW_ENGINE_CODEBASE_ALLOWED_ROOTS", str(tmp_path))
    monkeypatch.setattr(api_main, "_codebase_store", FakeStore())

    client = TestClient(api_main.app)
    response = client.post("/codebase/index", json={"root_path": str(source_dir)})

    assert response.status_code == 200
    payload = response.json()
    assert payload["indexed_files"] == 1
    assert payload["total_chunks"] >= 1
    assert indexed_chunks
