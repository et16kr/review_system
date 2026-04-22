from __future__ import annotations

from review_engine.config import Settings, get_settings
from review_engine.models import QueryAnalysis
from review_engine.query.detectors import QueryDetectorManager


def build_query_analysis(
    source_text: str,
    input_kind: str,
    *,
    settings: Settings | None = None,
    file_path: str | None = None,
    file_context: str | None = None,
    language_id: str = "cpp",
    profile_id: str | None = None,
    context_id: str | None = None,
    dialect_id: str | None = None,
    query_plugin_id: str | None = None,
    detector_refs: list[str] | None = None,
) -> QueryAnalysis:
    runtime_settings = settings or get_settings()
    selected_profile = profile_id or runtime_settings.default_profile_id
    selected_plugin = query_plugin_id or language_id
    manager = QueryDetectorManager(runtime_settings)
    patterns = manager.analyze(
        language_id=language_id,
        profile_id=selected_profile,
        query_plugin_id=selected_plugin,
        detector_refs=detector_refs,
        file_path=file_path,
        file_context=file_context,
        diff=source_text if input_kind == "diff" else None,
        code=source_text if input_kind == "code" else None,
    )
    query_text = manager.build_query_text(
        query_plugin_id=selected_plugin,
        input_kind=input_kind,
        patterns=patterns,
        profile_id=selected_profile,
        context_id=context_id,
        dialect_id=dialect_id,
    )
    return QueryAnalysis(
        input_kind=input_kind,
        language_id=language_id,
        profile_id=selected_profile,
        context_id=context_id,
        dialect_id=dialect_id,
        query_plugin_id=selected_plugin,
        detector_refs=list(detector_refs or []),
        query_text=query_text,
        patterns=patterns,
    )
