from __future__ import annotations

from review_engine.config import Settings, load_json_file
from review_engine.models import (
    ConflictResolutionResult,
    GuidelineRecord,
    PriorityPolicy,
    PriorityPolicyDefaults,
    PriorityPolicyExclusion,
    PriorityPolicyMatch,
    PriorityPolicyOverride,
)


def resolve_conflicts(
    records: list[GuidelineRecord], policy: PriorityPolicy | Settings
) -> ConflictResolutionResult:
    from review_engine.ingest.rule_loader import _resolve_records  # local import to avoid cycle

    resolved = _resolve_records(records, _coerce_policy(policy))
    all_records = [
        *resolved["active"],
        *resolved["reference"],
        *resolved["excluded"],
    ]
    return ConflictResolutionResult(
        all_records=all_records,
        active_records=resolved["active"],
        reference_records=resolved["reference"],
        excluded_records=resolved["excluded"],
    )


def _coerce_policy(policy: PriorityPolicy | Settings) -> PriorityPolicy:
    if isinstance(policy, PriorityPolicy):
        return policy
    return _legacy_policy_from_settings(policy)


def _legacy_policy_from_settings(settings: Settings) -> PriorityPolicy:
    pack_weights: dict[str, float] = {}
    if settings.source_priority_path and settings.source_priority_path.exists():
        payload = load_json_file(settings.source_priority_path)
        pack_weights = {
            str(pack_id): float(weight)
            for pack_id, weight in payload.get("authority_scores", {}).items()
        }

    disabled_rules: set[str] = set()
    exclusions: list[PriorityPolicyExclusion] = []
    if settings.disabled_cpp_rules_path and settings.disabled_cpp_rules_path.exists():
        payload = load_json_file(settings.disabled_cpp_rules_path)
        for rule_no in payload.get("disabled_rules", []):
            rule_no_text = str(rule_no)
            disabled_rules.add(rule_no_text)
            exclusions.append(
                PriorityPolicyExclusion(
                    match=PriorityPolicyMatch(rule_no=rule_no_text),
                    rationale="Legacy disabled C++ rule compatibility exclusion.",
                )
            )

    overrides: list[PriorityPolicyOverride] = []
    if settings.conflict_rules_path and settings.conflict_rules_path.exists():
        payload = load_json_file(settings.conflict_rules_path)
        for item in payload.get("explicit_rule_overrides", []):
            rule_no = item.get("rule_no")
            if not rule_no or str(rule_no) in disabled_rules:
                continue
            overrides.append(
                PriorityPolicyOverride(
                    match=PriorityPolicyMatch(rule_no=str(rule_no)),
                    action="overridden",
                    overridden_by=[str(rule_id) for rule_id in item.get("overridden_by", [])],
                    rationale=item.get("reason"),
                )
            )

    return PriorityPolicy(
        policy_id="legacy_compatibility",
        language_id="cpp",
        pack_weights=pack_weights,
        defaults=PriorityPolicyDefaults(default_pack_weight=0.5),
        overrides=overrides,
        exclusions=exclusions,
    )
