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
    active_records = [
        record for record in resolution.active_records if record.reviewability == "auto_review"
    ]
    reference_records = [
        record for record in resolution.active_records if record.reviewability != "auto_review"
    ]
    excluded_records = resolution.excluded_records

    write_json_file(
        settings.dataset_path("active"),
        [record.model_dump() for record in active_records],
    )
    write_json_file(
        settings.dataset_path("reference"),
        [record.model_dump() for record in reference_records],
    )
    write_json_file(
        settings.dataset_path("excluded"),
        [record.model_dump() for record in excluded_records],
    )

    ChromaGuidelineStore(settings).rebuild(
        active_records=active_records,
        reference_records=reference_records,
        excluded_records=excluded_records,
    )

    return IngestionSummary(
        total_parsed=len(all_records),
        altibase_records=len(parsed_altibase),
        cpp_core_records=len(parsed_cpp_core),
        active_records=len(active_records),
        reference_records=len(reference_records),
        excluded_records=len(excluded_records),
        source_html_cache=str(settings.cpp_core_html_cache),
        active_dataset_path=str(settings.dataset_path("active")),
        reference_dataset_path=str(settings.dataset_path("reference")),
        excluded_dataset_path=str(settings.dataset_path("excluded")),
        parsed_altibase_path=str(settings.parsed_altibase_path),
        parsed_cpp_core_path=str(settings.parsed_cpp_core_path),
        collections={
            settings.collection_for("active"): len(active_records),
            settings.collection_for("reference"): len(reference_records),
            settings.collection_for("excluded"): len(excluded_records),
        },
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
    source_priority = load_json_file(settings.source_priority_path)
    review_profiles = (
        load_json_file(settings.review_profiles_path) if settings.review_profiles_path else {}
    )
    authority_scores = source_priority["authority_scores"]
    default_policies = source_priority["default_conflict_policy"]

    records: list[GuidelineRecord] = []
    for rule in parsed_rules:
        authority = "internal" if rule.source_family == "altibase" else "external"
        severity = _score_severity(rule)
        priority = _score_priority(rule, severity, authority_scores[rule.source_family])
        review_meta = _build_review_metadata(rule, review_profiles, severity, priority)
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
                embedding_text=_build_embedding_text(
                    rule,
                    authority,
                    priority,
                    severity,
                    review_meta["category"],
                    review_meta["reviewability"],
                    review_meta["trigger_patterns"],
                    review_meta["fix_guidance"],
                ),
                reviewability=review_meta["reviewability"],
                applies_to=review_meta["applies_to"],
                category=review_meta["category"],
                false_positive_risk=review_meta["false_positive_risk"],
                trigger_patterns=review_meta["trigger_patterns"],
                bot_comment_template=review_meta["bot_comment_template"],
                fix_guidance=review_meta["fix_guidance"],
                review_rank_default=review_meta["review_rank_default"],
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
    rule: ParsedRule,
    authority: str,
    priority: float,
    severity: float,
    category: str,
    reviewability: str,
    trigger_patterns: list[str],
    fix_guidance: str | None,
) -> str:
    del authority, priority, severity
    return "\n".join(
        [
            f"rule_no: {rule.rule_no}",
            f"section: {rule.section}",
            f"title: {rule.title}",
            f"summary: {rule.summary}",
            f"keywords: {', '.join(rule.keywords)}",
            f"category: {category}",
            f"reviewability: {reviewability}",
            f"trigger_patterns: {', '.join(trigger_patterns)}",
            f"fix_guidance: {fix_guidance or ''}",
            f"text: {rule.text}",
        ]
    ).strip()


def _build_review_metadata(
    rule: ParsedRule,
    review_profiles: dict,
    severity: float,
    priority: float,
) -> dict[str, object]:
    section_profiles = review_profiles.get("section_profiles", {})
    rule_overrides = review_profiles.get("rule_overrides", {})
    profile = section_profiles.get(rule.section, {})
    profile = {**profile, **rule_overrides.get(rule.rule_no, {})}
    keyword_tokens = {token.lower() for token in rule.keywords}
    active_keywords = {token.lower() for token in review_profiles.get("active_keywords", [])}
    title_summary_tokens = f"{rule.title} {rule.summary} {rule.text}".lower()

    reviewability = str(profile.get("reviewability", "auto_review"))
    if rule.source_family == "cpp_core":
        if rule.section in review_profiles.get("external_reference_sections", []):
            reviewability = "reference_only"
        elif rule.section in review_profiles.get("external_auto_review_sections", []):
            if keyword_tokens & active_keywords or any(
                token in title_summary_tokens for token in active_keywords
            ):
                reviewability = "auto_review" if priority >= 0.72 else "manual_only"
            else:
                reviewability = "reference_only"
        else:
            reviewability = "reference_only"
    elif priority < 0.55 and reviewability == "auto_review":
        reviewability = "manual_only"

    summary = _clean_text(rule.summary)
    title = _clean_text(rule.title)
    if summary == title:
        summary = _derive_summary(rule.text, title)
    rule.summary = summary
    rule.title = title
    rule.text = _clean_text(rule.text)

    category = str(profile.get("category", _infer_category(rule)))
    false_positive_risk = str(profile.get("false_positive_risk", _infer_fp_risk(severity)))
    trigger_patterns = list(profile.get("trigger_patterns", _infer_trigger_patterns(rule)))
    fix_guidance = profile.get("fix_guidance") or _infer_fix_guidance(category)
    bot_comment_template = profile.get("bot_comment_template") or (
        "[봇 리뷰] {title}\n\n- 규칙: {rule_no}\n- 설명: {summary}\n- 권장 방향: {fix_guidance}"
    )
    review_rank_default = float(profile.get("review_rank_default", round(priority, 4)))
    return {
        "reviewability": reviewability,
        "applies_to": ["code", "diff"],
        "category": category,
        "false_positive_risk": false_positive_risk,
        "trigger_patterns": trigger_patterns,
        "bot_comment_template": bot_comment_template,
        "fix_guidance": fix_guidance,
        "review_rank_default": review_rank_default,
    }


def _clean_text(value: str) -> str:
    cleaned = value.replace("???", " ").replace("??", " ").strip()
    cleaned = " ".join(cleaned.split())
    return cleaned


def _derive_summary(text: str, fallback: str) -> str:
    cleaned = _clean_text(text)
    for separator in [". ", "\n", "; "]:
        if separator in cleaned:
            candidate = cleaned.split(separator, maxsplit=1)[0].strip()
            if candidate:
                return candidate
    return cleaned[:180] if cleaned else fallback


def _infer_category(rule: ParsedRule) -> str:
    section_map = {
        "ALTI-MEM": "memory",
        "ALTI-ERR": "error_handling",
        "ALTI-PCM": "wrapper_usage",
        "ALTI-PRE": "portability",
        "ALTI-TYC": "type_usage",
        "ALTI-COF": "control_flow",
        "ALTI-COM": "comment_usage",
        "ALTI-DCL": "format_usage",
        "Rule-R": "control_flow",
        "R": "memory",
        "E": "error_handling",
        "ES": "control_flow",
        "CP": "control_flow",
        "SF": "portability",
    }
    return section_map.get(rule.section, "general")


def _infer_fp_risk(severity: float) -> str:
    if severity >= 0.9:
        return "low"
    if severity >= 0.7:
        return "medium"
    return "high"


def _infer_trigger_patterns(rule: ParsedRule) -> list[str]:
    token_map = {
        "malloc": "malloc_free",
        "free": "malloc_free",
        "delete": "manual_delete",
        "ownership": "ownership_ambiguity",
        "switch": "switch_without_default",
        "continue": "continue_usage",
        "comment": "line_comment",
        "header": "direct_system_header",
        "include": "include_portability",
        "format": "primitive_format_specifier",
        "printf": "primitive_format_specifier",
        "error": "error_code_flow",
        "lock": "manual_lock_unlock",
    }
    inferred = []
    for keyword in rule.keywords:
        pattern = token_map.get(keyword.lower())
        if pattern and pattern not in inferred:
            inferred.append(pattern)
    return inferred


def _infer_fix_guidance(category: str) -> str:
    guidance = {
        "memory": (
            "Prefer RAII, clear ownership, and automatic cleanup over manual allocation paths."
        ),
        "error_handling": (
            "Keep success and failure paths explicit and align with the internal error macros."
        ),
        "wrapper_usage": (
            "Use approved internal wrapper APIs instead of direct system or libc calls."
        ),
        "portability": "Prefer the internal portability layer and portable include/type rules.",
        "control_flow": (
            "Make branch behavior explicit and avoid hidden or fragile control-flow shortcuts."
        ),
        "comment_usage": "Keep comments minimal but compliant with the internal required format.",
        "format_usage": "Use portable format helpers and avoid mismatched primitive specifiers.",
        "type_usage": "Use the approved internal type aliases for portability-sensitive paths.",
        "general": "Apply the guideline directly or fall back to the internal convention first.",
    }
    return guidance.get(category, guidance["general"])
