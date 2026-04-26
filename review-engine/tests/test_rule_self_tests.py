from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pytest
from pydantic import BaseModel, ConfigDict, Field, model_validator

from review_engine.ingest.rule_loader import _load_yaml
from review_engine.models import RulePackManifest
from review_engine.query.languages import BUILTIN_QUERY_PLUGINS
from review_engine.retrieve.applicability import DIRECT_CATEGORY_SIGNALS


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PROJECT_ROOT.parent
MANIFEST_PATH = PROJECT_ROOT / "examples/rule_self_tests/manifest.yaml"
MANIFEST_ROOT = MANIFEST_PATH.parent
COVERAGE_BASELINE_PATH = (
    REPO_ROOT / "docs/baselines/review_engine/rule_self_test_coverage_2026-04-26.md"
)

WaiverReason = Literal[
    "pending_backfill",
    "needs_detector",
    "semantic_only",
    "reference_only",
    "covered_by_group_case",
    "not_applicable_to_code",
    "pending_shared_host_validation",
]


@dataclass(frozen=True, order=True)
class RuleKey:
    language_id: str
    rule_no: str


@dataclass(frozen=True)
class RuleEntryInfo:
    reviewability: str
    category: str
    trigger_patterns: tuple[str, ...]
    source_path: Path


class RuleSelfTestCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    rule_no: str
    language_id: str
    rule_language_id: str | None = None
    profile_id: str | None = None
    context_id: str | None = None
    dialect_id: str | None = None
    reviewability: Literal["auto_review", "reference_only"]
    input_kind: Literal["code", "diff"]
    review_path: str | None = None
    violating_path: str
    compliant_path: str
    expected_patterns: list[str] = Field(default_factory=list)
    expected_rules: list[str] = Field(default_factory=list)
    forbidden_rules_in_violating: list[str] = Field(default_factory=list)
    forbidden_rules_in_compliant: list[str] = Field(default_factory=list)
    top_k: int = Field(default=12, gt=0)
    judgment: Literal["accepted"]
    judgment_note: str | None = None

    @model_validator(mode="after")
    def _validate_rule_expectations(self) -> RuleSelfTestCase:
        if self.reviewability == "auto_review":
            if self.rule_no not in self.expected_rules:
                raise ValueError("auto_review cases must include rule_no in expected_rules")
            if self.rule_no not in self.forbidden_rules_in_compliant:
                raise ValueError("auto_review cases must forbid rule_no in compliant results")
        if self.reviewability == "reference_only":
            if self.expected_rules:
                raise ValueError("reference_only cases must not expect auto-review results")
            if self.rule_no not in self.forbidden_rules_in_violating:
                raise ValueError("reference_only cases must forbid rule_no in violating results")
        return self


class RuleSelfTestWaiver(BaseModel):
    model_config = ConfigDict(extra="forbid")

    waiver_id: str
    language_id: str
    reviewability: Literal["auto_review", "reference_only"]
    reason: WaiverReason
    detail: str
    rule_nos: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_rule_nos_are_unique(self) -> RuleSelfTestWaiver:
        if len(self.rule_nos) != len(set(self.rule_nos)):
            raise ValueError(f"waiver {self.waiver_id} contains duplicate rule_nos")
        if self.reviewability == "reference_only" and self.reason != "reference_only":
            raise ValueError("reference_only waivers must use reason=reference_only")
        return self


class RuleSelfTestManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    cases: list[RuleSelfTestCase] = Field(default_factory=list)
    waivers: list[RuleSelfTestWaiver] = Field(default_factory=list)


def _load_manifest() -> RuleSelfTestManifest:
    return RuleSelfTestManifest.model_validate(_load_yaml(MANIFEST_PATH))


def _enabled_rule_entries() -> dict[RuleKey, RuleEntryInfo]:
    entries: dict[RuleKey, RuleEntryInfo] = {}
    for pack_path in sorted((PROJECT_ROOT / "rules").glob("*/packs/*.yaml")):
        pack = RulePackManifest.model_validate(_load_yaml(pack_path))
        for entry in pack.entries:
            if not entry.enabled:
                continue
            key = RuleKey(pack.language_id, entry.rule_no)
            if key in entries:
                existing = entries[key]
                raise AssertionError(
                    f"Duplicate enabled rule key {key}: "
                    f"{existing.source_path} and {pack_path}"
                )
            entries[key] = RuleEntryInfo(
                reviewability=entry.reviewability,
                category=entry.category,
                trigger_patterns=tuple(entry.trigger_patterns),
                source_path=pack_path,
            )
    return entries


def _case_key(case: RuleSelfTestCase) -> RuleKey:
    return RuleKey(case.rule_language_id or case.language_id, case.rule_no)


def _expected_rule_language_id(case: RuleSelfTestCase) -> str:
    return case.rule_language_id or case.language_id


def _waiver_keys(waiver: RuleSelfTestWaiver) -> set[RuleKey]:
    return {RuleKey(waiver.language_id, rule_no) for rule_no in waiver.rule_nos}


def _resolve_manifest_path(relative_path: str) -> Path:
    path = Path(relative_path)
    if path.is_absolute():
        raise AssertionError(f"manifest path must be relative: {relative_path}")
    resolved = (MANIFEST_ROOT / path).resolve()
    try:
        resolved.relative_to(PROJECT_ROOT.resolve())
    except ValueError as exc:
        raise AssertionError(f"manifest path escapes review-engine: {relative_path}") from exc
    if not resolved.exists():
        raise AssertionError(f"manifest path does not exist: {relative_path}")
    return resolved


def _validate_review_path(review_path: str | None) -> None:
    if review_path is None:
        return
    path = Path(review_path)
    if path.is_absolute() or any(part == ".." for part in path.parts):
        raise AssertionError(f"review_path must be repo-local: {review_path}")


def _parse_coverage_baseline() -> dict[str, int]:
    payload = COVERAGE_BASELINE_PATH.read_text(encoding="utf-8")
    metrics: dict[str, int] = {}
    for match in re.finditer(r"^- ([a-z0-9_]+): (\d+)$", payload, flags=re.MULTILINE):
        metrics[match.group(1)] = int(match.group(2))
    return metrics


def _direct_detector_backed_auto_keys() -> tuple[set[RuleKey], set[RuleKey]]:
    direct_keys: set[RuleKey] = set()
    gap_keys: set[RuleKey] = set()

    for key, entry in _enabled_rule_entries().items():
        if entry.reviewability != "auto_review" or key.language_id == "shared":
            continue
        plugin = BUILTIN_QUERY_PLUGINS[key.language_id]
        compatible_patterns = []
        for trigger_pattern in entry.trigger_patterns:
            if trigger_pattern not in plugin.direct_hint_patterns:
                continue
            if key.rule_no not in plugin.hinted_rules.get(trigger_pattern, ()):
                continue
            direct_signals = DIRECT_CATEGORY_SIGNALS.get(entry.category)
            if direct_signals is not None and trigger_pattern not in direct_signals:
                continue
            compatible_patterns.append(trigger_pattern)

        if compatible_patterns:
            direct_keys.add(key)
        else:
            gap_keys.add(key)

    return direct_keys, gap_keys


def _read_case_payload(case: RuleSelfTestCase, *, variant: Literal["violating", "compliant"]) -> str:
    relative_path = case.violating_path if variant == "violating" else case.compliant_path
    return _resolve_manifest_path(relative_path).read_text(encoding="utf-8")


def _review_case(real_search_service, case: RuleSelfTestCase, payload: str):
    if case.input_kind == "code":
        file_path = case.review_path or case.violating_path
    else:
        file_path = case.review_path
    kwargs = {
        "top_k": case.top_k,
        "file_path": file_path,
        "language_id": case.language_id,
        "profile_id": case.profile_id,
        "context_id": case.context_id,
        "dialect_id": case.dialect_id,
    }
    if case.input_kind == "diff":
        return real_search_service.review_diff(payload, **kwargs)
    return real_search_service.review_code(payload, **kwargs)


def _auto_review_cases() -> list[RuleSelfTestCase]:
    return [
        case
        for case in _load_manifest().cases
        if case.reviewability == "auto_review"
    ]


def _reference_only_cases() -> list[RuleSelfTestCase]:
    return [
        case
        for case in _load_manifest().cases
        if case.reviewability == "reference_only"
    ]


def test_rule_self_test_manifest_is_valid() -> None:
    manifest = _load_manifest()
    entries = _enabled_rule_entries()

    case_ids = [case.case_id for case in manifest.cases]
    assert len(case_ids) == len(set(case_ids))
    waiver_ids = [waiver.waiver_id for waiver in manifest.waivers]
    assert len(waiver_ids) == len(set(waiver_ids))

    for case in manifest.cases:
        _resolve_manifest_path(case.violating_path)
        _resolve_manifest_path(case.compliant_path)
        _validate_review_path(case.review_path)
        key = _case_key(case)
        assert key in entries, f"case references unknown enabled rule: {key}"
        assert entries[key].reviewability == case.reviewability
        for rule_no in sorted(set(case.expected_rules + case.forbidden_rules_in_compliant)):
            expected_key = RuleKey(_expected_rule_language_id(case), rule_no)
            assert expected_key in entries, (
                f"case references unknown expected/forbidden rule: {expected_key}"
            )

    for waiver in manifest.waivers:
        for key in _waiver_keys(waiver):
            assert key in entries, f"waiver references unknown enabled rule: {key}"
            assert entries[key].reviewability == waiver.reviewability


def test_every_enabled_rule_entry_is_accounted_for() -> None:
    manifest = _load_manifest()
    entries = _enabled_rule_entries()
    case_keys = {_case_key(case) for case in manifest.cases}
    all_waiver_keys = [
        key
        for waiver in manifest.waivers
        for key in _waiver_keys(waiver)
    ]
    waiver_keys = {
        key
        for key in all_waiver_keys
    }

    assert len(all_waiver_keys) == len(waiver_keys)
    assert case_keys.isdisjoint(waiver_keys)
    accounted_for = case_keys | waiver_keys
    missing = sorted(set(entries) - accounted_for)

    assert not missing, "Missing rule self-test case or waiver: " + ", ".join(
        f"{key.language_id}:{key.rule_no}" for key in missing
    )


def test_self_test_coverage_does_not_regress() -> None:
    manifest = _load_manifest()
    baseline = _parse_coverage_baseline()
    case_keys = {_case_key(case) for case in manifest.cases}
    direct_keys, gap_keys = _direct_detector_backed_auto_keys()
    missing_direct_cases = sorted(direct_keys - case_keys)
    pending_backfill_waivers = [
        waiver.waiver_id
        for waiver in manifest.waivers
        if waiver.reason == "pending_backfill"
    ]
    shared_host_pending_keys = {
        key
        for waiver in manifest.waivers
        if waiver.reason == "pending_shared_host_validation"
        for key in _waiver_keys(waiver)
    }
    shared_auto_keys = {
        key
        for key, entry in _enabled_rule_entries().items()
        if key.language_id == "shared" and entry.reviewability == "auto_review"
    }
    explicit_shared_case_keys = {
        RuleKey(_expected_rule_language_id(case), rule_no)
        for case in manifest.cases
        if case.language_id == "shared" and _expected_rule_language_id(case) == "shared"
        for rule_no in case.expected_rules
    }
    shared_host_case_keys = {
        RuleKey(_expected_rule_language_id(case), rule_no)
        for case in manifest.cases
        if case.language_id != "shared" and _expected_rule_language_id(case) == "shared"
        for rule_no in case.expected_rules
    }

    assert not missing_direct_cases, "Missing direct detector self-test case: " + ", ".join(
        f"{key.language_id}:{key.rule_no}" for key in missing_direct_cases
    )
    assert not pending_backfill_waivers
    assert {key.language_id for key in gap_keys} <= {"cpp"}
    assert len(direct_keys) >= baseline["reviewable_direct_detector_backed_auto_rules"]
    assert len(direct_keys & case_keys) >= baseline[
        "hard_gated_reviewable_direct_detector_backed_auto_rules"
    ]
    assert len(gap_keys) <= baseline["cxx_detector_gap_auto_rules"]
    assert shared_auto_keys <= explicit_shared_case_keys
    assert shared_auto_keys <= shared_host_case_keys
    assert not shared_host_pending_keys
    assert len(shared_host_pending_keys) <= baseline["shared_auto_rules_pending_host_validation"]
    assert len(shared_auto_keys & explicit_shared_case_keys) >= baseline[
        "shared_auto_rules_explicit_shared_cases"
    ]
    assert len(shared_auto_keys & shared_host_case_keys) >= baseline[
        "shared_auto_rules_host_language_validated"
    ]


@pytest.mark.parametrize("case", _auto_review_cases(), ids=lambda case: case.case_id)
def test_violating_cases_detect_expected_rules(real_search_service, case: RuleSelfTestCase) -> None:
    response = _review_case(
        real_search_service,
        case,
        _read_case_payload(case, variant="violating"),
    )

    returned_patterns = set(response.detected_patterns)
    returned_rule_languages = {result.rule_no: result.language_id for result in response.results}
    returned_rules = set(returned_rule_languages)

    assert response.language_id == case.language_id
    assert response.profile_id == case.profile_id
    assert response.context_id == case.context_id
    assert response.dialect_id == case.dialect_id
    assert set(case.expected_patterns) <= returned_patterns
    assert set(case.expected_rules) <= returned_rules
    for rule_no in case.expected_rules:
        assert returned_rule_languages[rule_no] == _expected_rule_language_id(case)


@pytest.mark.parametrize("case", _load_manifest().cases, ids=lambda case: case.case_id)
def test_compliant_cases_do_not_detect_forbidden_rules(
    real_search_service,
    case: RuleSelfTestCase,
) -> None:
    response = _review_case(
        real_search_service,
        case,
        _read_case_payload(case, variant="compliant"),
    )

    returned_rules = {result.rule_no for result in response.results}

    assert set(case.forbidden_rules_in_compliant).isdisjoint(returned_rules)


@pytest.mark.parametrize("case", _reference_only_cases(), ids=lambda case: case.case_id)
def test_reference_only_cases_are_not_auto_findings(
    real_search_service,
    case: RuleSelfTestCase,
) -> None:
    response = _review_case(
        real_search_service,
        case,
        _read_case_payload(case, variant="violating"),
    )
    returned_rules = {result.rule_no for result in response.results}
    inspected = real_search_service.inspect_rule(case.rule_no, language_id=case.language_id)

    assert set(case.forbidden_rules_in_violating).isdisjoint(returned_rules)
    assert inspected is not None
    assert inspected.reviewability == "reference_only"
