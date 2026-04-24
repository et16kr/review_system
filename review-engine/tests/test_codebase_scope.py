from __future__ import annotations

from pathlib import Path

from review_engine.api import main as api_main
from review_engine.codebase.store import CODEBASE_COLLECTION, CodebaseStore


def test_codebase_store_collection_name_is_project_scoped(fixture_settings) -> None:
    store = CodebaseStore(fixture_settings)

    default_collection = store._collection_name()
    smoke_collection = store._collection_name("root/review-system-smoke")
    other_collection = store._collection_name("root/another-project")

    assert default_collection == CODEBASE_COLLECTION
    assert smoke_collection.startswith(f"{CODEBASE_COLLECTION}_")
    assert smoke_collection != other_collection


def test_index_codebase_passes_project_ref_to_store(monkeypatch, tmp_path: Path) -> None:
    indexed_chunks: list[list[dict[str, object]]] = []
    indexed_project_refs: list[str | None] = []

    class FakeStore:
        def clear(self, *, project_ref: str | None = None) -> None:
            return None

        def upsert_chunks(
            self,
            chunks: list[dict[str, object]],
            *,
            project_ref: str | None = None,
        ) -> int:
            indexed_chunks.append(chunks)
            indexed_project_refs.append(project_ref)
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

    payload = api_main.index_codebase(
        api_main.CodebaseIndexRequest(
            root_path=str(source_dir),
            project_ref="root/review-system-smoke",
        )
    )

    assert payload["indexed_files"] == 1
    assert payload["total_chunks"] >= 1
    assert payload["project_ref"] == "root/review-system-smoke"
    assert indexed_chunks
    assert indexed_project_refs == ["root/review-system-smoke"]


def test_search_codebase_passes_project_ref_to_store(monkeypatch) -> None:
    search_calls: list[dict[str, object]] = []

    class FakeStore:
        def search(
            self,
            query: str,
            top_k: int = 3,
            *,
            project_ref: str | None = None,
        ) -> list[dict[str, object]]:
            search_calls.append(
                {
                    "query": query,
                    "top_k": top_k,
                    "project_ref": project_ref,
                }
            )
            return [
                {
                    "file_path": "src/a.cpp",
                    "func_name": "legacyAlloc",
                    "start_line": 7,
                    "snippet": "char* p = (char*)malloc(size);",
                    "similarity": 0.82,
                }
            ]

    monkeypatch.setattr(api_main, "_codebase_store", FakeStore())

    payload = api_main.search_codebase(
        api_main.CodebaseSearchRequest(
            query="malloc buffer allocation",
            top_k=2,
            project_ref="root/review-system-smoke",
        )
    )

    assert payload["results"][0]["file_path"] == "src/a.cpp"
    assert search_calls == [
        {
            "query": "malloc buffer allocation",
            "top_k": 2,
            "project_ref": "root/review-system-smoke",
        }
    ]
