from __future__ import annotations

from review_engine.config import Settings, load_json_file, write_json_file
from review_engine.ingest.chroma_store import ChromaGuidelineStore
from review_engine.ingest.rule_loader import discover_rule_languages, load_rule_runtime
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
    "secret",
    "injection",
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
    "context",
    "permission",
    "root",
}
MEDIUM_PRIORITY_TERMS = {
    "copy",
    "move",
    "const",
    "style",
    "layout",
    "comment",
    "naming",
    "typing",
    "async",
    "cleanup",
}


def ingest_all_sources(settings: Settings, force_refresh: bool = False) -> IngestionSummary:
    del force_refresh
    languages = discover_rule_languages(settings) or [settings.default_language_id]
    store = ChromaGuidelineStore(settings)

    total_parsed = 0
    total_active = 0
    total_reference = 0
    total_excluded = 0
    aggregate_collections: dict[str, int] = {}
    aggregate_pack_counts: dict[str, int] = {}
    language_summaries: dict[str, dict[str, int | str]] = {}
    dataset_paths: dict[str, dict[str, str]] = {}
    default_runtime = None

    for language_id in languages:
        runtime = load_rule_runtime(
            settings,
            language_id=language_id,
            include_all_packs=True,
        )
        if default_runtime is None and language_id == settings.default_language_id:
            default_runtime = runtime

        active_path = settings.dataset_path("active", language_id)
        reference_path = settings.dataset_path("reference", language_id)
        excluded_path = settings.dataset_path("excluded", language_id)
        write_json_file(active_path, [record.model_dump() for record in runtime.active_records])
        write_json_file(reference_path, [record.model_dump() for record in runtime.reference_records])
        write_json_file(excluded_path, [record.model_dump() for record in runtime.excluded_records])

        store.rebuild_language(
            language_id=language_id,
            active_records=runtime.active_records,
            reference_records=runtime.reference_records,
            excluded_records=runtime.excluded_records,
        )

        parsed_total = sum(runtime.parsed_pack_counts.values())
        total_parsed += parsed_total
        total_active += len(runtime.active_records)
        total_reference += len(runtime.reference_records)
        total_excluded += len(runtime.excluded_records)
        aggregate_pack_counts.update(runtime.parsed_pack_counts)
        aggregate_collections.update(
            {
                settings.collection_for("active", language_id): len(runtime.active_records),
                settings.collection_for("reference", language_id): len(runtime.reference_records),
                settings.collection_for("excluded", language_id): len(runtime.excluded_records),
            }
        )
        language_summaries[language_id] = {
            "parsed": parsed_total,
            "active": len(runtime.active_records),
            "reference": len(runtime.reference_records),
            "excluded": len(runtime.excluded_records),
        }
        dataset_paths[language_id] = {
            "active": str(active_path),
            "reference": str(reference_path),
            "excluded": str(excluded_path),
        }

    default_runtime = default_runtime or load_rule_runtime(
        settings,
        language_id=settings.default_language_id,
        include_all_packs=True,
    )
    return IngestionSummary(
        total_parsed=total_parsed,
        altibase_records=0,
        cpp_core_records=aggregate_pack_counts.get("cpp_core", 0),
        active_records=total_active,
        reference_records=total_reference,
        excluded_records=total_excluded,
        active_dataset_path=str(settings.dataset_path("active")),
        reference_dataset_path=str(settings.dataset_path("reference")),
        excluded_dataset_path=str(settings.dataset_path("excluded")),
        collections=aggregate_collections,
        parsed_pack_counts=aggregate_pack_counts,
        public_rule_root=default_runtime.public_rule_root,
        extension_rule_roots=default_runtime.extension_rule_roots,
        languages=language_summaries,
        dataset_paths=dataset_paths,
    )


def load_active_records(settings: Settings, language_id: str | None = None) -> list[GuidelineRecord]:
    active_path = settings.dataset_path("active", language_id)
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
        source_kind = (
            "organization_policy"
            if (rule.source_family or "").startswith("alti")
            else "public_standard"
        )
        priority_tier = "override" if source_kind == "organization_policy" else "default"
        pack_weight = 1.0 if source_kind == "organization_policy" else 0.72
        severity = _score_severity(rule)
        base_score = _score_base(rule, severity, pack_weight)
        records.append(
            GuidelineRecord(
                id=f"{(rule.pack_id or rule.source_family or 'unknown')}:{rule.rule_no}",
                rule_uid=f"{rule.language_id}:{(rule.pack_id or rule.source_family or 'unknown')}:{rule.rule_no}",
                rule_no=rule.rule_no,
                source=rule.source,
                pack_id=rule.pack_id or rule.source_family or "unknown",
                rule_pack=rule.pack_id or rule.source_family or "unknown",
                source_kind=source_kind,
                language_id=rule.language_id,
                context_id=rule.context_id,
                dialect_id=rule.dialect_id,
                namespace=rule.namespace,
                section=rule.section,
                title=rule.title,
                text=rule.text,
                summary=rule.summary,
                keywords=rule.keywords,
                tags=rule.tags,
                base_score=base_score,
                priority_tier=priority_tier,
                pack_weight=pack_weight,
                specificity=0.5,
                severity_default=severity,
                conflict_action="compatible",
                reviewability="auto_review"
                if source_kind == "organization_policy"
                else "reference_only",
                category=_infer_category(rule),
                false_positive_risk=_infer_fp_risk(severity),
                trigger_patterns=_infer_trigger_patterns(rule),
                fix_guidance=_infer_fix_guidance(_infer_category(rule)),
                review_rank_default=round(base_score, 4),
            )
        )
    return records


def _score_severity(rule: ParsedRule) -> float:
    tokens = set(rule.keywords) | set(rule.tags)
    if tokens & VERY_HIGH_PRIORITY_TERMS:
        return 0.95
    if tokens & HIGH_PRIORITY_TERMS:
        return 0.82
    if tokens & MEDIUM_PRIORITY_TERMS:
        return 0.64
    return 0.48


def _score_base(rule: ParsedRule, severity: float, pack_weight: float) -> float:
    section_boost = 0.0
    if rule.section.startswith(("R", "CP", "E", "ES", "SEC", "CFG", "SQL")):
        section_boost = 0.06
    return round(min(1.0, severity * 0.7 + pack_weight * 0.2 + section_boost), 4)


def _infer_category(rule: ParsedRule) -> str:
    title_text = f"{rule.section} {rule.title} {rule.summary}".lower()
    if any(token in title_text for token in {"malloc", "free", "new", "delete", "ownership", "raii"}):
        return "memory"
    if any(token in title_text for token in {"lock", "unlock", "wrapper"}):
        return "wrapper_usage"
    if any(token in title_text for token in {"switch", "continue", "loop", "goto"}):
        return "control_flow"
    if any(token in title_text for token in {"header", "portable", "include"}):
        return "portability"
    if any(token in title_text for token in {"type", "typed", "pointer"}):
        return "type_usage"
    if any(token in title_text for token in {"printf", "variadic", "format"}):
        return "format_usage"
    if any(token in title_text for token in {"secret", "privilege", "injection", "shell"}):
        return "security"
    if any(token in title_text for token in {"yaml", "manifest", "docker", "container"}):
        return "configuration"
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
    if "printf" in title_text or "variadic" in title_text or "format" in title_text:
        patterns.extend(["primitive_format_specifier", "direct_system_call"])
    if "type" in title_text:
        patterns.append("primitive_types")
    if "move" in title_text:
        patterns.append("return_move_local")
    if "secret" in title_text:
        patterns.append("hardcoded_secret")
    if "shell" in title_text:
        patterns.append("shell_injection")
    if "sql" in title_text:
        patterns.append("sql_injection")
    deduped: list[str] = []
    for pattern in patterns:
        if pattern not in deduped:
            deduped.append(pattern)
    return deduped


def _infer_fix_guidance(category: str) -> str | None:
    guidance = {
        "memory": "Prefer explicit ownership, scoped cleanup, and standard resource-management helpers.",
        "wrapper_usage": "Wrap low-level behavior in a safer, narrower abstraction.",
        "control_flow": "Prefer clearer guard structure and fewer surprising control-flow branches.",
        "portability": "Prefer portable interfaces and project-approved compatibility wrappers.",
        "type_usage": "Use stronger types and clearer API contracts instead of ambiguous primitives.",
        "format_usage": "Prefer typed formatting or safer formatting helpers.",
        "security": "Move secrets or command/query construction behind explicit trust boundaries and safer APIs.",
        "configuration": "Prefer explicit, least-privilege, and schema-aligned configuration defaults.",
    }
    return guidance.get(category)
