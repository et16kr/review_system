from __future__ import annotations

from typing import Any

import chromadb

from app.config import Settings
from app.models import CandidateHit, GuidelineRecord
from app.retrieve.embeddings import HashingEmbedder


class ChromaGuidelineStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.embedder = HashingEmbedder()
        self.client = chromadb.PersistentClient(path=str(settings.chroma_path))

    def rebuild(self, records: list[GuidelineRecord]) -> None:
        existing = {collection.name for collection in self.client.list_collections()}
        if self.settings.collection_name in existing:
            self.client.delete_collection(self.settings.collection_name)

        collection = self.client.create_collection(
            name=self.settings.collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        collection.add(
            ids=[record.id for record in records],
            documents=[record.embedding_text for record in records],
            embeddings=self.embedder.embed_documents([record.embedding_text for record in records]),
            metadatas=[record.chroma_metadata() for record in records],
        )

    def query(self, query_text: str, top_n: int = 30) -> list[CandidateHit]:
        collection = self.client.get_collection(self.settings.collection_name)
        response = collection.query(
            query_embeddings=[self.embedder.embed_query(query_text)],
            n_results=top_n,
            include=["distances", "documents", "metadatas"],
        )

        candidates: list[CandidateHit] = []
        metadatas = response.get("metadatas", [[]])[0]
        documents = response.get("documents", [[]])[0]
        distances = response.get("distances", [[]])[0]
        for metadata, document, distance in zip(metadatas, documents, distances, strict=False):
            record = _record_from_chroma(metadata, document)
            candidates.append(
                CandidateHit(
                    record=record,
                    distance=float(distance),
                    similarity_score=max(0.0, 1.0 - float(distance)),
                )
            )
        return candidates

    def get_rule(self, rule_no: str) -> GuidelineRecord | None:
        collection = self.client.get_collection(self.settings.collection_name)
        response = collection.get(where={"rule_no": rule_no}, include=["documents", "metadatas"])
        if not response.get("ids"):
            return None
        return _record_from_chroma(response["metadatas"][0], response["documents"][0])

    def get_rules(self, rule_nos: list[str]) -> list[GuidelineRecord]:
        records: list[GuidelineRecord] = []
        for rule_no in rule_nos:
            record = self.get_rule(rule_no)
            if record is not None:
                records.append(record)
        return records


def _record_from_chroma(metadata: dict[str, Any], document: str) -> GuidelineRecord:
    return GuidelineRecord(
        id=f"{metadata['source_family']}:{metadata['rule_no']}",
        rule_no=str(metadata["rule_no"]),
        source=str(metadata["source"]),
        source_family=str(metadata["source_family"]),
        authority=str(metadata["authority"]),
        section=str(metadata["section"]),
        title=str(metadata["title"]),
        text=str(metadata["text"]),
        summary=str(metadata["summary"]),
        keywords=[token for token in str(metadata.get("keywords", "")).split(",") if token],
        priority=float(metadata["priority"]),
        severity_default=float(metadata["severity_default"]),
        conflict_policy=str(metadata["conflict_policy"]),
        embedding_text=document,
        overridden_by=[
            token for token in str(metadata.get("overridden_by", "")).split(",") if token
        ],
        conflict_reason=str(metadata.get("conflict_reason", "")) or None,
        active=bool(metadata.get("active", True)),
    )
