from __future__ import annotations

from app.config import Settings, load_json_file, write_json_file
from app.ingest.chroma_store import ChromaGuidelineStore
from app.ingest.conflict_resolver import resolve_conflicts
from app.models import GuidelineRecord, IngestionSummary, ParsedRule
from app.parser.guidelines_fetcher import CPP_CORE_GUIDELINES_URL, fetch_cpp_core_guidelines
from app.parser.guidelines_parser import parse_cpp_core_guidelines
from app.parser.internal_convention_parser import parse_internal_convention

VERY_HIGH_PRIORITY_TERMS = {
    "ownership",
    "lifetime",
    "leak",
    "dangling",
    "null",
    "mutex",
    "lock",
    "unlock",
    "error",
    "exception",
    "malloc",
    "free",
    "delete",
    "portability",
}
HIGH_PRIORITY_TERMS = {
    "raii",
    "resource",
    "unsafe",
    "header",
    "include",
    "system",
    "format",
    "wrapper",
    "pointer",
    "memory",
    "switch",
    "continue",
    "primitive",
    "typedef",
    "macro",
}
MEDIUM_PRIORITY_TERMS = {
    "copy",
    "move",
    "const",
    "style",
    "layout",
    "comment",
    "naming",
}


def ingest_all_sources(settings: Settings, force_refresh: bool = False) -> IngestionSummary:
    internal_markdown = settings.internal_guideline_path.read_text(encoding="utf-8")
    parsed_altibase = parse_internal_convention(
        internal_markdown, source=str(settings.internal_guideline_path)
    )

    cpp_html = fetch_cpp_core_guidelines(settings, force_refresh=force_refresh)
    parsed_cpp_core = parse_cpp_core_guidelines(cpp_html, source=CPP_CORE_GUIDELINES_URL)

    write_json_file(
        settings.parsed_altibase_path,
        [record.model_dump() for record in parsed_altibase],
    )
    write_json_file(
        settings.parsed_cpp_core_path,
        [record.model_dump() for record in parsed_cpp_core],
    )

    all_records = build_guideline_records(parsed_altibase + parsed_cpp_core, settings)
    resolution = resolve_conflicts(all_records, settings)
    write_json_file(
        settings.active_dataset_path,
        [record.model_dump() for record in resolution.active_records],
    )

    ChromaGuidelineStore(settings).rebuild(resolution.active_records)

    return IngestionSummary(
        total_parsed=len(all_records),
        altibase_records=len(parsed_altibase),
        cpp_core_records=len(parsed_cpp_core),
        active_records=len(resolution.active_records),
        excluded_records=len(resolution.excluded_records),
        source_html_cache=str(settings.cpp_core_html_cache),
        active_dataset_path=str(settings.active_dataset_path),
        parsed_altibase_path=str(settings.parsed_altibase_path),
        parsed_cpp_core_path=str(settings.parsed_cpp_core_path),
    )


def load_active_records(settings: Settings) -> list[GuidelineRecord]:
    if not settings.active_dataset_path.exists():
        return []
    payload = load_json_file(settings.active_dataset_path)
    return [GuidelineRecord.model_validate(item) for item in payload]


def build_guideline_records(
    parsed_rules: list[ParsedRule], settings: Settings
) -> list[GuidelineRecord]:
    source_priority = load_json_file(settings.source_priority_path)
    authority_scores = source_priority["authority_scores"]
    default_policies = source_priority["default_conflict_policy"]

    records: list[GuidelineRecord] = []
    for rule in parsed_rules:
        authority = "internal" if rule.source_family == "altibase" else "external"
        severity = _score_severity(rule)
        priority = _score_priority(rule, severity, authority_scores[rule.source_family])
        records.append(
            GuidelineRecord(
                id=f"{rule.source_family}:{rule.rule_no}",
                rule_no=rule.rule_no,
                source=rule.source,
                source_family=rule.source_family,
                authority=authority,
                section=rule.section,
                title=rule.title,
                text=rule.text,
                summary=rule.summary,
                keywords=rule.keywords,
                priority=priority,
                severity_default=severity,
                conflict_policy=default_policies[rule.source_family],
                embedding_text=_build_embedding_text(rule, authority, priority, severity),
            )
        )
    return records


def _score_severity(rule: ParsedRule) -> float:
    tokens = set(rule.keywords)
    if tokens & VERY_HIGH_PRIORITY_TERMS:
        return 0.95
    if tokens & HIGH_PRIORITY_TERMS:
        return 0.82
    if tokens & MEDIUM_PRIORITY_TERMS:
        return 0.64
    return 0.48


def _score_priority(rule: ParsedRule, severity: float, authority_score: float) -> float:
    section_boost = 0.0
    if rule.section in {"ALTI-ERR", "ALTI-MEM", "ALTI-PCM", "R", "CP"}:
        section_boost = 0.08
    if rule.source_family == "altibase":
        section_boost += 0.06
    return round(min(1.0, severity * 0.7 + authority_score * 0.3 + section_boost), 4)


def _build_embedding_text(
    rule: ParsedRule, authority: str, priority: float, severity: float
) -> str:
    del authority, priority, severity
    return "\n".join(
        [
            f"rule_no: {rule.rule_no}",
            f"section: {rule.section}",
            f"title: {rule.title}",
            f"summary: {rule.summary}",
            f"keywords: {', '.join(rule.keywords)}",
            f"text: {rule.text}",
        ]
    ).strip()
