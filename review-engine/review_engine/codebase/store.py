from __future__ import annotations

import hashlib
from typing import Any

from review_engine.config import Settings
from review_engine.retrieve.embeddings import HashingEmbedder

CODEBASE_COLLECTION = "codebase_chunks"


class CodebaseStore:
    """저장소 코드 청크를 ChromaDB에 저장하고 검색한다."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.embedder = HashingEmbedder()
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            import chromadb

            if self.settings.chroma_host:
                try:
                    self._client = chromadb.HttpClient(
                        host=self.settings.chroma_host,
                        port=self.settings.chroma_port,
                    )
                    return self._client
                except Exception:
                    pass
            self._client = chromadb.PersistentClient(path=str(self.settings.chroma_path))
        return self._client

    def _collection_name(self, project_ref: str | None = None) -> str:
        normalized_project_ref = (project_ref or "").strip()
        if not normalized_project_ref:
            return CODEBASE_COLLECTION
        project_hash = hashlib.sha1(
            normalized_project_ref.encode("utf-8")
        ).hexdigest()[:12]
        return f"{CODEBASE_COLLECTION}_{project_hash}"

    def _get_or_create_collection(self, project_ref: str | None = None) -> Any:
        collection_name = self._collection_name(project_ref)
        client = self._get_client()
        existing = {c.name for c in client.list_collections()}
        if collection_name not in existing:
            return client.create_collection(collection_name)
        return client.get_collection(collection_name)

    def upsert_chunks(self, chunks: list[dict], *, project_ref: str | None = None) -> int:
        if not chunks:
            return 0
        collection = self._get_or_create_collection(project_ref)
        ids, docs, metas = [], [], []
        for chunk in chunks:
            chunk_id = f"{chunk['file_path']}:{chunk['start_line']}"
            ids.append(chunk_id)
            docs.append(chunk["text"])
            metas.append(
                {
                    "file_path": chunk["file_path"],
                    "func_name": chunk.get("func_name", ""),
                    "start_line": chunk.get("start_line", 0),
                }
            )
        embeddings = self.embedder.embed_documents(docs)
        collection.upsert(ids=ids, embeddings=embeddings, documents=docs, metadatas=metas)
        return len(ids)

    def search(self, query: str, top_k: int = 3, *, project_ref: str | None = None) -> list[dict]:
        try:
            collection = self._get_or_create_collection(project_ref)
            n = collection.count()
            if n == 0:
                return []
            result = collection.query(
                query_embeddings=[self.embedder.embed_query(query)],
                n_results=min(top_k, n),
                include=["documents", "metadatas", "distances"],
            )
            hits = []
            for doc, meta, dist in zip(
                result["documents"][0],
                result["metadatas"][0],
                result["distances"][0],
            ):
                hits.append(
                    {
                        "file_path": meta.get("file_path", ""),
                        "func_name": meta.get("func_name", ""),
                        "start_line": meta.get("start_line", 0),
                        "snippet": doc,
                        "similarity": max(0.0, 1.0 - dist),
                    }
                )
            return hits
        except Exception:
            return []

    def clear(self, *, project_ref: str | None = None) -> None:
        client = self._get_client()
        existing = {c.name for c in client.list_collections()}
        collection_name = self._collection_name(project_ref)
        if collection_name in existing:
            client.delete_collection(collection_name)
