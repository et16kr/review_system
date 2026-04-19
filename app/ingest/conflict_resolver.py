from __future__ import annotations

from app.config import Settings, load_json_file
from app.models import ConflictResolutionResult, GuidelineRecord


def resolve_conflicts(
    records: list[GuidelineRecord], settings: Settings
) -> ConflictResolutionResult:
    disabled_rules = set(load_json_file(settings.disabled_cpp_rules_path)["disabled_rules"])
    conflict_config = load_json_file(settings.conflict_rules_path)
    explicit_overrides = {
        item["rule_no"]: item for item in conflict_config.get("explicit_rule_overrides", [])
    }
    keyword_overrides = conflict_config.get("keyword_overrides", [])

    resolved: list[GuidelineRecord] = []
    active_records: list[GuidelineRecord] = []
    excluded_records: list[GuidelineRecord] = []

    for record in records:
        updated = record.model_copy(deep=True)
        if updated.source_family == "altibase":
            updated.conflict_policy = "authoritative"
            updated.active = True
        else:
            if updated.rule_no in disabled_rules:
                updated.conflict_policy = "excluded"
                updated.active = False
                updated.conflict_reason = "Rule disabled by explicit configuration."
            elif updated.rule_no in explicit_overrides:
                override = explicit_overrides[updated.rule_no]
                updated.conflict_policy = "overridden"
                updated.active = False
                updated.overridden_by = override.get("overridden_by", [])
                updated.conflict_reason = override.get("reason")
            else:
                haystack = " ".join(
                    [updated.title, updated.text, " ".join(updated.keywords)]
                ).lower()
                for override in keyword_overrides:
                    matches = override.get("match_any", [])
                    if any(keyword.lower() in haystack for keyword in matches):
                        updated.conflict_policy = "overridden"
                        updated.active = False
                        updated.overridden_by = override.get("overridden_by", [])
                        updated.conflict_reason = override.get("reason")
                        break

        resolved.append(updated)
        if updated.active:
            active_records.append(updated)
        else:
            excluded_records.append(updated)

    return ConflictResolutionResult(
        all_records=resolved,
        active_records=active_records,
        excluded_records=excluded_records,
    )
