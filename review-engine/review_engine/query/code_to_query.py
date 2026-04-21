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
    detector_refs: list[str] | None = None,
) -> QueryAnalysis:
    runtime_settings = settings or get_settings()
    selected_profile = profile_id or runtime_settings.default_profile_id
    manager = QueryDetectorManager(runtime_settings)
    patterns = manager.analyze(
        language_id=language_id,
        profile_id=selected_profile,
        detector_refs=detector_refs,
        file_path=file_path,
        file_context=file_context,
        diff=source_text if input_kind == "diff" else None,
        code=source_text if input_kind == "code" else None,
    )
    if patterns:
        concerns = " ".join(pattern.description for pattern in patterns)
        query_text = f"Review this {language_id.upper()} {input_kind} for the following likely issues. {concerns}"
    else:
        query_text = (
            f"Review this {language_id.upper()} {input_kind} for resource management issues, "
            "strong typing and portability concerns, control-flow hazards, and relevant public "
            "guideline recommendations."
        )

    return QueryAnalysis(
        input_kind=input_kind,
        language_id=language_id,
        profile_id=selected_profile,
        detector_refs=list(detector_refs or []),
        query_text=query_text,
        patterns=patterns,
    )
