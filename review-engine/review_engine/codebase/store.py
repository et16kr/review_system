from __future__ import annotations

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

    def _get_or_create_collection(self) -> Any:
        client = self._get_client()
        existing = {c.name for c in client.list_collections()}
        if CODEBASE_COLLECTION not in existing:
            return client.create_collection(CODEBASE_COLLECTION)
        return client.get_collection(CODEBASE_COLLECTION)

    def upsert_chunks(self, chunks: list[dict]) -> int:
        if not chunks:
            return 0
        collection = self._get_or_create_collection()
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

    def search(self, query: str, top_k: int = 3) -> list[dict]:
        try:
            collection = self._get_or_create_collection()
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

    def clear(self) -> None:
        client = self._get_client()
        existing = {c.name for c in client.list_collections()}
        if CODEBASE_COLLECTION in existing:
            client.delete_collection(CODEBASE_COLLECTION)
