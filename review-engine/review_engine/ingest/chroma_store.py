from __future__ import annotations

from typing import Any

import chromadb

from review_engine.config import Settings
from review_engine.models import CandidateHit, GuidelineRecord
from review_engine.retrieve.embeddings import HashingEmbedder


class ChromaGuidelineStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.embedder = HashingEmbedder()
        self.client = self._build_client()

    def _build_client(self) -> Any:
        settings = self.settings
        if settings.chroma_host:
            try:
                return chromadb.HttpClient(
                    host=settings.chroma_host,
                    port=settings.chroma_port,
                )
            except Exception:
                pass
        return chromadb.PersistentClient(path=str(settings.chroma_path))

    def rebuild(
        self,
        *,
        active_records: list[GuidelineRecord],
        reference_records: list[GuidelineRecord],
        excluded_records: list[GuidelineRecord],
    ) -> None:
        existing = {collection.name for collection in self.client.list_collections()}
        for kind in ("active", "reference", "excluded"):
            collection_name = self.settings.collection_for(kind)
            if collection_name in existing:
                self.client.delete_collection(collection_name)

        self._write_collection("active", active_records)
        self._write_collection("reference", reference_records)
        self._write_collection("excluded", excluded_records)

    def query(self, query_text: str, top_n: int = 30) -> list[CandidateHit]:
        collection = self.client.get_collection(self.settings.collection_for("active"))
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
        for kind in ("active", "reference", "excluded"):
            collection = self.client.get_collection(self.settings.collection_for(kind))
            response = collection.get(
                where={"rule_no": rule_no},
                include=["documents", "metadatas"],
            )
            if response.get("ids"):
                return _record_from_chroma(response["metadatas"][0], response["documents"][0])
        return None

    def get_rules(self, rule_nos: list[str]) -> list[GuidelineRecord]:
        records: list[GuidelineRecord] = []
        for rule_no in rule_nos:
            collection = self.client.get_collection(self.settings.collection_for("active"))
            response = collection.get(
                where={"rule_no": rule_no},
                include=["documents", "metadatas"],
            )
            record = None
            if response.get("ids"):
                record = _record_from_chroma(response["metadatas"][0], response["documents"][0])
            if record is not None:
                records.append(record)
        return records

    def _write_collection(self, kind: str, records: list[GuidelineRecord]) -> None:
        collection_name = self.settings.collection_for(kind)
        self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        if not records:
            return
        collection = self.client.get_collection(collection_name)
        collection.add(
            ids=[record.id for record in records],
            documents=[record.embedding_text for record in records],
            embeddings=self.embedder.embed_documents([record.embedding_text for record in records]),
            metadatas=[record.chroma_metadata() for record in records],
        )


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
        reviewability=str(metadata.get("reviewability", "auto_review")),
        applies_to=[token for token in str(metadata.get("applies_to", "")).split(",") if token],
        category=str(metadata.get("category", "general")),
        false_positive_risk=str(metadata.get("false_positive_risk", "medium")),
        trigger_patterns=[
            token for token in str(metadata.get("trigger_patterns", "")).split(",") if token
        ],
        bot_comment_template=str(metadata.get("bot_comment_template", "")) or None,
        fix_guidance=str(metadata.get("fix_guidance", "")) or None,
        review_rank_default=float(metadata.get("review_rank_default", 0.5)),
    )
