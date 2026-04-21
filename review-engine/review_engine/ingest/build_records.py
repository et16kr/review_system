from __future__ import annotations

from review_engine.config import Settings, load_json_file, write_json_file
from review_engine.ingest.chroma_store import ChromaGuidelineStore
from review_engine.ingest.rule_loader import load_rule_runtime
from review_engine.models import GuidelineRecord, IngestionSummary, ParsedRule

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
    del force_refresh
    runtime = load_rule_runtime(settings)

    write_json_file(
        settings.dataset_path("active"),
        [record.model_dump() for record in runtime.active_records],
    )
    write_json_file(
        settings.dataset_path("reference"),
        [record.model_dump() for record in runtime.reference_records],
    )
    write_json_file(
        settings.dataset_path("excluded"),
        [record.model_dump() for record in runtime.excluded_records],
    )

    ChromaGuidelineStore(settings).rebuild(
        active_records=runtime.active_records,
        reference_records=runtime.reference_records,
        excluded_records=runtime.excluded_records,
    )

    return IngestionSummary(
        total_parsed=sum(runtime.parsed_pack_counts.values()),
        altibase_records=0,
        cpp_core_records=runtime.parsed_pack_counts.get("cpp_core", 0),
        active_records=len(runtime.active_records),
        reference_records=len(runtime.reference_records),
        excluded_records=len(runtime.excluded_records),
        active_dataset_path=str(settings.dataset_path("active")),
        reference_dataset_path=str(settings.dataset_path("reference")),
        excluded_dataset_path=str(settings.dataset_path("excluded")),
        collections={
            settings.collection_for("active"): len(runtime.active_records),
            settings.collection_for("reference"): len(runtime.reference_records),
            settings.collection_for("excluded"): len(runtime.excluded_records),
        },
        parsed_pack_counts=runtime.parsed_pack_counts,
        public_rule_root=runtime.public_rule_root,
        extension_rule_roots=runtime.extension_rule_roots,
    )


def load_active_records(settings: Settings) -> list[GuidelineRecord]:
    active_path = settings.dataset_path("active")
    if not active_path.exists():
        return []
    payload = load_json_file(active_path)
    return [GuidelineRecord.model_validate(item) for item in payload]


def build_guideline_records(
    parsed_rules: list[ParsedRule], settings: Settings
) -> list[GuidelineRecord]:
    del settings
    records: list[GuidelineRecord] = []
    for rule in parsed_rules:
        source_kind = "organization_policy" if (rule.source_family or "").startswith("alti") else "public_standard"
        priority_tier = "override" if source_kind == "organization_policy" else "default"
        pack_weight = 1.0 if source_kind == "organization_policy" else 0.72
        severity = _score_severity(rule)
        base_score = _score_base(rule, severity, pack_weight)
        records.append(
            GuidelineRecord(
                id=f"{(rule.pack_id or rule.source_family or 'unknown')}:{rule.rule_no}",
                rule_no=rule.rule_no,
                source=rule.source,
                pack_id=rule.pack_id or rule.source_family or "unknown",
                source_kind=source_kind,
                language_id=rule.language_id,
                namespace=rule.namespace,
                section=rule.section,
                title=rule.title,
                text=rule.text,
                summary=rule.summary,
                keywords=rule.keywords,
                base_score=base_score,
                priority_tier=priority_tier,
                pack_weight=pack_weight,
                specificity=0.5,
                severity_default=severity,
                conflict_action="compatible",
                reviewability="auto_review" if source_kind == "organization_policy" else "reference_only",
                category=_infer_category(rule),
                false_positive_risk=_infer_fp_risk(severity),
                trigger_patterns=_infer_trigger_patterns(rule),
                fix_guidance=_infer_fix_guidance(_infer_category(rule)),
                review_rank_default=round(base_score, 4),
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


def _score_base(rule: ParsedRule, severity: float, pack_weight: float) -> float:
    section_boost = 0.0
    if rule.section.startswith(("R", "CP", "E", "ES")):
        section_boost = 0.06
    return round(min(1.0, severity * 0.7 + pack_weight * 0.2 + section_boost), 4)


def _infer_category(rule: ParsedRule) -> str:
    title_text = f"{rule.section} {rule.title} {rule.summary}".lower()
    if any(token in title_text for token in {"malloc", "free", "new", "delete", "ownership", "raii"}):
        return "memory"
    if any(token in title_text for token in {"lock", "unlock"}):
        return "wrapper_usage"
    if any(token in title_text for token in {"switch", "continue", "loop", "goto"}):
        return "control_flow"
    if any(token in title_text for token in {"header", "portable", "include"}):
        return "portability"
    if any(token in title_text for token in {"type", "typed", "pointer"}):
        return "type_usage"
    if any(token in title_text for token in {"printf", "iostream", "variadic", "format"}):
        return "format_usage"
    return "general"


def _infer_fp_risk(severity: float) -> str:
    if severity >= 0.9:
        return "low"
    if severity >= 0.7:
        return "medium"
    return "high"


def _infer_trigger_patterns(rule: ParsedRule) -> list[str]:
    title_text = f"{rule.section} {rule.title} {rule.summary}".lower()
    patterns: list[str] = []
    if any(token in title_text for token in {"malloc", "free"}):
        patterns.append("malloc_free")
    if any(token in title_text for token in {"new", "delete", "ownership"}):
        patterns.extend(["raw_new", "manual_delete", "ownership_ambiguity"])
    if "lock" in title_text or "unlock" in title_text:
        patterns.append("manual_lock_unlock")
    if "continue" in title_text:
        patterns.append("continue_usage")
    if "switch" in title_text or "default" in title_text:
        patterns.append("switch_without_default")
    if "header" in title_text or "include" in title_text:
        patterns.append("direct_system_header")
    if "printf" in title_text or "variadic" in title_text or "iostream" in title_text:
        patterns.extend(["primitive_format_specifier", "direct_system_call"])
    if "type" in title_text:
        patterns.append("primitive_types")
    if "move" in title_text:
        patterns.append("return_move_local")
    deduped: list[str] = []
    for pattern in patterns:
        if pattern not in deduped:
            deduped.append(pattern)
    return deduped


def _infer_fix_guidance(category: str) -> str | None:
    guidance = {
        "memory": "Prefer RAII and standard smart-pointer/container types to manage ownership.",
        "wrapper_usage": "Wrap low-level resource management in safer scoped abstractions.",
        "control_flow": "Prefer explicit, readable control flow with clear exits and guards.",
        "portability": "Use portable includes and interfaces that stay within standard C++ conventions.",
        "type_usage": "Use precise, strongly typed interfaces instead of ambiguous raw representations.",
        "format_usage": "Prefer safer, typed formatting and I/O facilities over C-style interfaces.",
    }
    return guidance.get(category)
