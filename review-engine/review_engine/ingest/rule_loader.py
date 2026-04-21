from __future__ import annotations

from pathlib import Path

import yaml

from review_engine.config import Settings
from review_engine.extensions import discover_extension_specs
from review_engine.models import (
    GuidelineRecord,
    LoadedRuleContext,
    PriorityPolicy,
    ProfileConfig,
    RuleEntry,
    RulePackManifest,
    RuleRootManifest,
)
from review_engine.text_utils import extract_keywords


def load_rule_runtime(settings: Settings) -> LoadedRuleContext:
    public_root = (settings.public_rule_root or (settings.project_root / "rules" / "cpp")).resolve()
    extension_rule_roots = [
        root
        for spec in discover_extension_specs(settings)
        for root in spec.rule_roots
    ]
    roots = [public_root, *extension_rule_roots]

    pack_index: dict[str, tuple[RulePackManifest, Path]] = {}
    profile_candidates: list[ProfileConfig] = []
    policy_index: dict[str, PriorityPolicy] = {}

    for root in roots:
        manifest = _load_rule_root_manifest(root)
        for relative in manifest.pack_files:
            path = root / relative
            pack = RulePackManifest.model_validate(_load_yaml(path))
            pack_index[pack.pack_id] = (pack, path)
        for relative in manifest.profile_files:
            path = root / relative
            profile_candidates.append(ProfileConfig.model_validate(_load_yaml(path)))
        for relative in manifest.policy_files:
            path = root / relative
            policy = PriorityPolicy.model_validate(_load_yaml(path))
            policy_index[policy.policy_id] = policy

    profile = _merge_profiles(
        [
            candidate
            for candidate in profile_candidates
            if candidate.profile_id == settings.default_profile_id
            and candidate.language_id == settings.default_language_id
        ]
    )
    policy = policy_index[profile.priority_policy_ref]

    selected_pack_ids = _dedupe(profile.enabled_packs + profile.shared_packs)
    if not selected_pack_ids:
        selected_pack_ids = [
            pack_id
            for pack_id, (pack, _path) in pack_index.items()
            if pack.default_enabled and pack.language_id == settings.default_language_id
        ]

    all_records: list[GuidelineRecord] = []
    parsed_pack_counts: dict[str, int] = {}
    for pack_id in selected_pack_ids:
        pack, source_path = pack_index[pack_id]
        parsed_pack_counts[pack_id] = len(pack.entries)
        for entry in pack.entries:
            all_records.append(_build_record(pack, entry, source_path, policy))

    resolved = _resolve_records(all_records, policy)
    return LoadedRuleContext(
        language_id=settings.default_language_id,
        profile=profile,
        policy=policy,
        active_records=resolved["active"],
        reference_records=resolved["reference"],
        excluded_records=resolved["excluded"],
        parsed_pack_counts=parsed_pack_counts,
        public_rule_root=str(public_root),
        extension_rule_roots=[str(root) for root in extension_rule_roots],
        prompt_overlay_refs=list(profile.prompt_overlay_refs),
        detector_refs=list(profile.detector_refs),
    )


def _load_rule_root_manifest(root: Path) -> RuleRootManifest:
    return RuleRootManifest.model_validate(_load_yaml(root / "manifest.yaml"))


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _merge_profiles(candidates: list[ProfileConfig]) -> ProfileConfig:
    if not candidates:
        raise ValueError("No profile config matched the selected runtime profile.")
    merged = candidates[0].model_copy(deep=True)
    for candidate in candidates[1:]:
        merged.enabled_packs = _dedupe(merged.enabled_packs + candidate.enabled_packs)
        merged.shared_packs = _dedupe(merged.shared_packs + candidate.shared_packs)
        merged.prompt_overlay_refs = _dedupe(
            merged.prompt_overlay_refs + candidate.prompt_overlay_refs
        )
        merged.detector_refs = _dedupe(merged.detector_refs + candidate.detector_refs)
        if candidate.priority_policy_ref:
            merged.priority_policy_ref = candidate.priority_policy_ref
    return merged


def _build_record(
    pack: RulePackManifest,
    entry: RuleEntry,
    source_path: Path,
    policy: PriorityPolicy,
) -> GuidelineRecord:
    keywords = entry.keywords or extract_keywords(
        f"{entry.rule_no} {entry.title} {entry.summary} {entry.text}"
    )
    base_score = entry.base_score if entry.base_score is not None else 0.6
    severity_default = entry.severity_default if entry.severity_default is not None else base_score
    priority_tier = entry.priority_tier or pack.default_priority_tier
    pack_weight = float(policy.pack_weights.get(pack.pack_id, policy.defaults.default_pack_weight))
    return GuidelineRecord(
        id=f"{pack.pack_id}:{entry.rule_no}",
        rule_no=entry.rule_no,
        source=str(source_path),
        pack_id=pack.pack_id,
        source_kind=pack.source_kind,
        language_id=pack.language_id,
        namespace=pack.namespace,
        section=entry.section,
        title=entry.title,
        text=entry.text,
        summary=entry.summary,
        keywords=keywords,
        base_score=base_score,
        priority_tier=priority_tier,
        pack_weight=pack_weight,
        specificity=entry.specificity,
        severity_default=severity_default,
        conflict_action=entry.default_action,
        reviewability=entry.reviewability,
        applies_to=entry.applies_to,
        category=entry.category,
        false_positive_risk=entry.false_positive_risk,
        trigger_patterns=entry.trigger_patterns,
        bot_comment_template=entry.bot_comment_template,
        fix_guidance=entry.fix_guidance,
        review_rank_default=entry.review_rank_default if entry.review_rank_default is not None else base_score,
        conflict_reason=entry.rationale,
    )


def _resolve_records(
    records: list[GuidelineRecord],
    policy: PriorityPolicy,
) -> dict[str, list[GuidelineRecord]]:
    all_records = [record.model_copy(deep=True) for record in records]
    explicit_override_ids = {
        overridden_id
        for override in policy.overrides
        for overridden_id in override.overridden_by
    }
    for record in all_records:
        record_id = record.id or f"{record.pack_id}:{record.rule_no}"
        if record_id in explicit_override_ids:
            record.explicit_override = True

    for exclusion in policy.exclusions:
        for record in all_records:
            if _matches(record, exclusion.match):
                record.conflict_action = "excluded"
                record.conflict_reason = exclusion.rationale
                record.active = False

    for override in policy.overrides:
        for record in all_records:
            if _matches(record, override.match):
                record.conflict_action = override.action
                record.conflict_reason = override.rationale
                record.overridden_by = list(override.overridden_by)
                record.active = False

    active: list[GuidelineRecord] = []
    reference: list[GuidelineRecord] = []
    excluded: list[GuidelineRecord] = []
    for record in all_records:
        record.conflict_policy = None
        record.priority = None
        record.embedding_text = None
        record = GuidelineRecord.model_validate(record.model_dump())
        if record.conflict_action in {"excluded", "overridden"}:
            excluded.append(record)
            continue
        if record.conflict_action == "reference_only" or record.reviewability != "auto_review":
            reference.append(record)
            continue
        active.append(record)
    return {"active": active, "reference": reference, "excluded": excluded}


def _matches(record: GuidelineRecord, selector) -> bool:
    if selector.rule_id and selector.rule_id != record.id:
        return False
    if selector.rule_no and selector.rule_no != record.rule_no:
        return False
    if selector.pack_id and selector.pack_id != record.pack_id:
        return False
    return any((selector.rule_id, selector.rule_no, selector.pack_id))


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered
