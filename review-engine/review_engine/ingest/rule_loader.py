from __future__ import annotations

from pathlib import Path

import yaml

from review_engine.config import Settings
from review_engine.extensions import discover_extension_specs
from review_engine.languages import get_language_registry
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


def load_rule_runtime(
    settings: Settings,
    *,
    language_id: str | None = None,
    profile_id: str | None = None,
    context_id: str | None = None,
    dialect_id: str | None = None,
    include_all_packs: bool = False,
) -> LoadedRuleContext:
    runtime, _selected_pack_index = load_rule_runtime_selection(
        settings,
        language_id=language_id,
        profile_id=profile_id,
        context_id=context_id,
        dialect_id=dialect_id,
        include_all_packs=include_all_packs,
    )
    return runtime


def load_rule_runtime_selection(
    settings: Settings,
    *,
    language_id: str | None = None,
    profile_id: str | None = None,
    context_id: str | None = None,
    dialect_id: str | None = None,
    include_all_packs: bool = False,
) -> tuple[LoadedRuleContext, dict[str, tuple[RulePackManifest, Path]]]:
    registry = get_language_registry()
    selected_language = language_id or settings.default_language_id
    default_profile_id = profile_id or _default_profile_for_language(
        settings,
        selected_language=selected_language,
    )
    public_root = (settings.public_rule_root or (settings.project_root / "rules")).resolve()
    extension_root_bases = [
        root
        for spec in discover_extension_specs(settings)
        for root in spec.rule_roots
    ]
    roots = _dedupe_paths(
        _resolve_roots_for_language(public_root, selected_language)
        + [
            resolved_root
            for root in extension_root_bases
            for resolved_root in _resolve_roots_for_language(root, selected_language)
        ]
    )

    pack_index: dict[str, tuple[RulePackManifest, Path]] = {}
    profile_candidates: list[ProfileConfig] = []
    policy_index: dict[str, PriorityPolicy] = {}

    for root in roots:
        manifest = _load_rule_root_manifest(root)
        for relative in manifest.pack_files:
            path = root / relative
            pack = RulePackManifest.model_validate(_load_yaml(path))
            if pack.language_id not in {selected_language, "shared"}:
                continue
            _add_pack_to_index(
                pack_index,
                pack=pack,
                path=path,
                selected_language=selected_language,
            )
        for relative in manifest.profile_files:
            path = root / relative
            profile = ProfileConfig.model_validate(_load_yaml(path))
            if profile.language_id == selected_language:
                profile_candidates.append(profile)
        for relative in manifest.policy_files:
            path = root / relative
            policy = PriorityPolicy.model_validate(_load_yaml(path))
            if policy.language_id in {selected_language, "shared"}:
                policy_index[policy.policy_id] = policy

    profile = _merge_profiles(
        profile_id=default_profile_id,
        language_id=selected_language,
        context_id=context_id,
        dialect_id=dialect_id,
        candidates=profile_candidates,
    )
    policy = policy_index.get(profile.priority_policy_ref)
    if policy is None:
        policy = PriorityPolicy(
            policy_id=f"{selected_language}_default",
            language_id=selected_language,
        )

    if include_all_packs:
        selected_pack_ids = [
            pack_id
            for pack_id, (pack, _path) in pack_index.items()
            if pack.language_id in {selected_language, "shared"}
        ]
    else:
        explicit_pack_ids = profile.enabled_packs + profile.shared_packs
        selected_pack_ids = _dedupe(explicit_pack_ids)
        if selected_pack_ids:
            _validate_selected_pack_ids(
                selected_pack_ids,
                pack_index=pack_index,
                profile=profile,
            )
        else:
            selected_pack_ids = [
                pack_id
                for pack_id, (pack, _path) in pack_index.items()
                if pack.default_enabled and pack.language_id in {selected_language, "shared"}
            ]

    all_records: list[GuidelineRecord] = []
    parsed_pack_counts: dict[str, int] = {}
    selected_pack_index: dict[str, tuple[RulePackManifest, Path]] = {}
    for pack_id in selected_pack_ids:
        pack_and_path = pack_index.get(pack_id)
        if pack_and_path is None:
            continue
        pack, source_path = pack_and_path
        selected_pack_index[pack_id] = (pack, source_path)
        parsed_pack_counts[pack_id] = len(pack.entries)
        for entry in pack.entries:
            if not entry.enabled:
                continue
            all_records.append(
                _build_record(
                    pack,
                    entry,
                    source_path,
                    policy,
                    context_id=context_id,
                    dialect_id=dialect_id,
                )
            )

    resolved = _resolve_records(all_records, policy)
    shared_pack_ids = [
        pack_id
        for pack_id in selected_pack_ids
        if pack_index.get(pack_id, (None, None))[0] is not None
        and pack_index[pack_id][0].language_id == "shared"
    ]
    runtime = LoadedRuleContext(
        language_id=selected_language,
        profile=profile,
        policy=policy,
        context_id=context_id,
        dialect_id=dialect_id,
        selected_pack_ids=selected_pack_ids,
        shared_pack_ids=shared_pack_ids,
        active_records=resolved["active"],
        reference_records=resolved["reference"],
        excluded_records=resolved["excluded"],
        parsed_pack_counts=parsed_pack_counts,
        public_rule_root=str(public_root),
        extension_rule_roots=[str(root) for root in extension_root_bases],
        prompt_overlay_refs=list(profile.prompt_overlay_refs),
        detector_refs=list(profile.detector_refs),
    )
    return runtime, selected_pack_index


def discover_rule_languages(settings: Settings) -> list[str]:
    registry = get_language_registry()
    discovered: set[str] = set()
    public_root = (settings.public_rule_root or (settings.project_root / "rules")).resolve()
    for language_id in registry.reviewable_languages():
        if _resolve_roots_for_language(public_root, language_id):
            discovered.add(language_id)
    for spec in discover_extension_specs(settings):
        for root in spec.rule_roots:
            for language_id in registry.reviewable_languages():
                if _resolve_roots_for_language(root, language_id):
                    discovered.add(language_id)
    return sorted(discovered)


def _resolve_roots_for_language(root: Path, language_id: str) -> list[Path]:
    resolved = root.expanduser().resolve()
    direct_manifest = resolved / "manifest.yaml"
    if direct_manifest.exists():
        manifest = RuleRootManifest.model_validate(_load_yaml(direct_manifest))
        if manifest.language_id in {language_id, "shared"}:
            return [resolved]
        return []

    candidates: list[Path] = []
    for name in ("shared", language_id):
        candidate = resolved / name
        if (candidate / "manifest.yaml").exists():
            candidates.append(candidate.resolve())
    return candidates


def _load_rule_root_manifest(root: Path) -> RuleRootManifest:
    return RuleRootManifest.model_validate(_load_yaml(root / "manifest.yaml"))


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _default_profile_for_language(settings: Settings, *, selected_language: str) -> str:
    registry_default = get_language_registry().get(selected_language).default_profile
    if selected_language == settings.default_language_id:
        return settings.default_profile_id or registry_default
    return registry_default


def _add_pack_to_index(
    pack_index: dict[str, tuple[RulePackManifest, Path]],
    *,
    pack: RulePackManifest,
    path: Path,
    selected_language: str,
) -> None:
    existing = pack_index.get(pack.pack_id)
    if existing is not None:
        _existing_pack, existing_path = existing
        raise ValueError(
            f"Duplicate rule pack id {pack.pack_id!r} for language "
            f"{selected_language!r}: {existing_path} and {path}. "
            "Explicit extension replacement is not supported."
        )
    pack_index[pack.pack_id] = (pack, path)


def _validate_selected_pack_ids(
    selected_pack_ids: list[str],
    *,
    pack_index: dict[str, tuple[RulePackManifest, Path]],
    profile: ProfileConfig,
) -> None:
    missing_pack_ids = [
        pack_id for pack_id in selected_pack_ids if pack_id not in pack_index
    ]
    if missing_pack_ids:
        missing = ", ".join(missing_pack_ids)
        raise ValueError(
            f"Profile {profile.profile_id!r} for language {profile.language_id!r} "
            "selects unknown rule pack ids from enabled_packs/shared_packs: "
            f"{missing}"
        )


def _merge_profiles(
    *,
    profile_id: str,
    language_id: str,
    context_id: str | None,
    dialect_id: str | None,
    candidates: list[ProfileConfig],
) -> ProfileConfig:
    matching = [
        candidate
        for candidate in candidates
        if candidate.profile_id == profile_id
        and candidate.language_id == language_id
        and (candidate.context_id in {None, context_id})
        and (candidate.dialect_id in {None, dialect_id})
    ]
    if not matching:
        return ProfileConfig(
            profile_id=profile_id,
            language_id=language_id,
            context_id=context_id,
            dialect_id=dialect_id,
            priority_policy_ref=f"{language_id}_default",
        )

    matching.sort(
        key=lambda item: (
            1 if item.context_id else 0,
            1 if item.dialect_id else 0,
        )
    )
    merged = matching[0].model_copy(deep=True)
    for candidate in matching[1:]:
        merged.enabled_packs = _dedupe(merged.enabled_packs + candidate.enabled_packs)
        merged.shared_packs = _dedupe(merged.shared_packs + candidate.shared_packs)
        merged.prompt_overlay_refs = _dedupe(
            merged.prompt_overlay_refs + candidate.prompt_overlay_refs
        )
        merged.detector_refs = _dedupe(merged.detector_refs + candidate.detector_refs)
        if candidate.priority_policy_ref:
            merged.priority_policy_ref = candidate.priority_policy_ref
        if candidate.context_id:
            merged.context_id = candidate.context_id
        if candidate.dialect_id:
            merged.dialect_id = candidate.dialect_id
    return merged


def _build_record(
    pack: RulePackManifest,
    entry: RuleEntry,
    source_path: Path,
    policy: PriorityPolicy,
    *,
    context_id: str | None,
    dialect_id: str | None,
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
        rule_uid=f"{pack.language_id}:{pack.pack_id}:{entry.rule_no}",
        rule_no=entry.rule_no,
        source=str(source_path),
        pack_id=pack.pack_id,
        rule_pack=pack.pack_id,
        source_kind=pack.source_kind,
        language_id=pack.language_id,
        context_id=entry.context_id or pack.context_id or context_id,
        dialect_id=entry.dialect_id or pack.dialect_id or dialect_id,
        namespace=pack.namespace,
        section=entry.section,
        title=entry.title,
        text=entry.text,
        summary=entry.summary,
        keywords=keywords,
        tags=entry.tags,
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
        review_rank_default=(
            entry.review_rank_default
            if entry.review_rank_default is not None
            else base_score
        ),
        conflict_reason=entry.rationale,
        file_globs=entry.file_globs or pack.file_globs,
        symbol_hints=entry.symbol_hints,
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


def _dedupe_paths(items: list[Path]) -> list[Path]:
    seen: set[Path] = set()
    ordered: list[Path] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered
