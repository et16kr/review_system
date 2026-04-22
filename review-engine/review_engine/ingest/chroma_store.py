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
        self.rebuild_language(
            language_id=self.settings.default_language_id,
            active_records=active_records,
            reference_records=reference_records,
            excluded_records=excluded_records,
        )

    def rebuild_language(
        self,
        *,
        language_id: str,
        active_records: list[GuidelineRecord],
        reference_records: list[GuidelineRecord],
        excluded_records: list[GuidelineRecord],
    ) -> None:
        existing = {collection.name for collection in self.client.list_collections()}
        for kind in ("active", "reference", "excluded"):
            collection_name = self.settings.collection_for(kind, language_id)
            if collection_name in existing:
                self.client.delete_collection(collection_name)

        self._write_collection("active", language_id, active_records)
        self._write_collection("reference", language_id, reference_records)
        self._write_collection("excluded", language_id, excluded_records)

    def query(
        self,
        query_text: str,
        *,
        language_id: str | None = None,
        top_n: int = 30,
    ) -> list[CandidateHit]:
        candidates: list[CandidateHit] = []
        for query_language in _query_languages(language_id or self.settings.default_language_id):
            collection = self._maybe_get_collection(self.settings.collection_for("active", query_language))
            if collection is None:
                continue
            response = collection.query(
                query_embeddings=[self.embedder.embed_query(query_text)],
                n_results=top_n,
                include=["distances", "documents", "metadatas"],
            )

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

    def get_rule(self, rule_no: str, *, language_id: str | None = None) -> GuidelineRecord | None:
        languages = _query_languages(language_id) if language_id else self.available_languages()
        for kind in ("active", "reference", "excluded"):
            for query_language in languages:
                collection = self._maybe_get_collection(self.settings.collection_for(kind, query_language))
                if collection is None:
                    continue
                response = collection.get(
                    where={"rule_no": rule_no},
                    include=["documents", "metadatas"],
                )
                if response.get("ids"):
                    return _record_from_chroma(response["metadatas"][0], response["documents"][0])
        return None

    def get_rules(self, rule_nos: list[str], *, language_id: str | None = None) -> list[GuidelineRecord]:
        records: list[GuidelineRecord] = []
        languages = _query_languages(language_id) if language_id else self.available_languages()
        for rule_no in rule_nos:
            record = None
            for query_language in languages:
                collection = self._maybe_get_collection(
                    self.settings.collection_for("active", query_language)
                )
                if collection is None:
                    continue
                response = collection.get(
                    where={"rule_no": rule_no},
                    include=["documents", "metadatas"],
                )
                if response.get("ids"):
                    record = _record_from_chroma(response["metadatas"][0], response["documents"][0])
                    break
            if record is not None:
                records.append(record)
        return records

    def has_collection(self, kind: str, language_id: str | None = None) -> bool:
        target_language = language_id or self.settings.default_language_id
        return self._maybe_get_collection(self.settings.collection_for(kind, target_language)) is not None

    def has_runtime_data(self, language_id: str | None = None) -> bool:
        target_language = language_id or self.settings.default_language_id
        return self.has_collection("active", target_language)

    def available_languages(self) -> list[str]:
        languages: set[str] = set()
        prefix = f"{self.settings.collection_name}_active_"
        for collection in self.client.list_collections():
            if collection.name.startswith(prefix):
                languages.add(collection.name.removeprefix(prefix))
            elif collection.name == self.settings.collection_for("active", self.settings.default_language_id):
                languages.add(self.settings.default_language_id)
        return sorted(languages)

    def _write_collection(self, kind: str, language_id: str, records: list[GuidelineRecord]) -> None:
        collection_name = self.settings.collection_for(kind, language_id)
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

    def _maybe_get_collection(self, name: str):
        try:
            return self.client.get_collection(name)
        except Exception:
            return None


def _query_languages(language_id: str | None) -> list[str]:
    if not language_id or language_id == "shared":
        return ["shared"]
    return [language_id, "shared"]


def _record_from_chroma(metadata: dict[str, Any], document: str) -> GuidelineRecord:
    return GuidelineRecord(
        id=str(metadata.get("id") or f"{metadata.get('pack_id') or metadata.get('source_family')}:{metadata['rule_no']}"),
        rule_uid=str(metadata.get("rule_uid") or metadata.get("id") or ""),
        rule_no=str(metadata["rule_no"]),
        source=str(metadata["source"]),
        pack_id=str(metadata.get("pack_id") or metadata.get("source_family") or ""),
        rule_pack=str(metadata.get("rule_pack") or metadata.get("pack_id") or ""),
        source_kind=str(metadata.get("source_kind", "public_standard")),
        language_id=str(metadata.get("language_id", "cpp")),
        context_id=str(metadata.get("context_id", "")) or None,
        dialect_id=str(metadata.get("dialect_id", "")) or None,
        namespace=str(metadata.get("namespace", "public")),
        source_family=str(metadata.get("source_family") or metadata.get("pack_id") or ""),
        authority=str(metadata.get("authority", "")),
        section=str(metadata["section"]),
        title=str(metadata["title"]),
        text=str(metadata["text"]),
        summary=str(metadata["summary"]),
        keywords=[token for token in str(metadata.get("keywords", "")).split(",") if token],
        tags=[token for token in str(metadata.get("tags", "")).split(",") if token],
        base_score=float(metadata.get("base_score", metadata.get("priority", 0.5))),
        priority_tier=str(metadata.get("priority_tier", "default")),
        pack_weight=float(metadata.get("pack_weight", 0.5)),
        specificity=float(metadata.get("specificity", 0.5)),
        explicit_override=bool(metadata.get("explicit_override", False)),
        priority=float(metadata.get("priority", metadata.get("base_score", 0.5))),
        severity_default=float(metadata.get("severity_default", 0.5)),
        conflict_action=str(metadata.get("conflict_action", "compatible")),
        conflict_policy=str(metadata.get("conflict_policy", "")),
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
        file_globs=[token for token in str(metadata.get("file_globs", "")).split(",") if token],
        symbol_hints=[token for token in str(metadata.get("symbol_hints", "")).split(",") if token],
    )
