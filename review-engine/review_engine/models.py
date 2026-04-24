from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


PriorityTier = Literal["reference", "default", "high", "override"]
ConflictAction = Literal["compatible", "overridden", "excluded", "reference_only"]
Reviewability = Literal["auto_review", "manual_only", "reference_only"]
AppliesTo = Literal["code", "diff", "comment", "docs"]

_PACKAGE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
)
_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def _legacy_authority(source_kind: str) -> str:
    if source_kind in {"organization_policy", "project_policy"}:
        return "internal"
    return "external"


def _legacy_conflict_policy(conflict_action: str, priority_tier: str) -> str:
    if priority_tier == "override" and conflict_action == "compatible":
        return "authoritative"
    return conflict_action


def _default_namespace(source_kind: str) -> str:
    if source_kind == "project_policy":
        return "project"
    if source_kind == "organization_policy":
        return "organization"
    return "public"


def _normalize_pack_identity(pack_id: str | None, source_family: str | None) -> tuple[str, str]:
    if pack_id and source_family and pack_id != source_family:
        raise ValueError(
            "source_family is a legacy alias of pack_id and must match when both are provided"
        )
    canonical_pack_id = pack_id or source_family or "unknown"
    return canonical_pack_id, canonical_pack_id


def _build_embedding_text(
    *,
    rule_no: str,
    section: str,
    title: str,
    summary: str,
    keywords: list[str],
    category: str,
    reviewability: str,
    trigger_patterns: list[str],
    fix_guidance: str | None,
    text: str,
    pack_id: str,
    language_id: str,
    context_id: str | None,
    dialect_id: str | None,
) -> str:
    return "\n".join(
        [
            f"rule_no: {rule_no}",
            f"pack_id: {pack_id}",
            f"language_id: {language_id}",
            f"context_id: {context_id or ''}",
            f"dialect_id: {dialect_id or ''}",
            f"section: {section}",
            f"title: {title}",
            f"summary: {summary}",
            f"keywords: {', '.join(keywords)}",
            f"category: {category}",
            f"reviewability: {reviewability}",
            f"trigger_patterns: {', '.join(trigger_patterns)}",
            f"fix_guidance: {fix_guidance or ''}",
            f"text: {text}",
        ]
    ).strip()


class StrictAuthoringModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RuleEntry(StrictAuthoringModel):
    rule_no: str
    section: str
    title: str
    text: str
    summary: str
    keywords: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    category: str = "general"
    reviewability: Reviewability = "auto_review"
    applies_to: list[AppliesTo] = Field(default_factory=lambda: ["code", "diff"])
    false_positive_risk: Literal["low", "medium", "high"] = "medium"
    trigger_patterns: list[str] = Field(default_factory=list)
    symbol_hints: list[str] = Field(default_factory=list)
    file_globs: list[str] = Field(default_factory=list)
    fix_guidance: str | None = None
    bot_comment_template: str | None = None
    review_rank_default: float | None = None
    base_score: float | None = None
    severity_default: float | None = None
    priority_tier: PriorityTier | None = None
    specificity: float = 0.5
    stability: float = 0.5
    default_action: ConflictAction = "compatible"
    overrides: list[str] = Field(default_factory=list)
    excluded_by: list[str] = Field(default_factory=list)
    rationale: str | None = None
    enabled: bool = True
    context_id: str | None = None
    dialect_id: str | None = None

    @model_validator(mode="after")
    def _enforce_canonical_operational_surface(self) -> RuleEntry:
        if self.default_action == "compatible":
            return self
        if self.default_action == "reference_only":
            raise ValueError(
                "default_action must stay compatible; use reviewability: reference_only for reference guidance"
            )
        raise ValueError(
            "default_action must stay compatible; use priority policy overrides/exclusions for conflict actions"
        )


class RulePackManifest(StrictAuthoringModel):
    schema_version: int = 1
    pack_id: str
    namespace: str = "public"
    language_id: str = "cpp"
    source_kind: str = "public_standard"
    description: str = ""
    default_enabled: bool = True
    default_priority_tier: PriorityTier = "default"
    profile_tags: list[str] = Field(default_factory=list)
    plugin_refs: list[str] = Field(default_factory=list)
    context_id: str | None = None
    dialect_id: str | None = None
    file_globs: list[str] = Field(default_factory=list)
    entries: list[RuleEntry] = Field(default_factory=list)


class ProfileConfig(StrictAuthoringModel):
    schema_version: int = 1
    profile_id: str
    language_id: str = "cpp"
    enabled_packs: list[str] = Field(default_factory=list)
    shared_packs: list[str] = Field(default_factory=list)
    prompt_overlay_refs: list[str] = Field(default_factory=list)
    detector_refs: list[str] = Field(default_factory=list)
    priority_policy_ref: str = "cpp_default"
    context_id: str | None = None
    dialect_id: str | None = None


class PriorityPolicyMatch(StrictAuthoringModel):
    rule_id: str | None = None
    rule_no: str | None = None
    pack_id: str | None = None


class PriorityPolicyOverride(StrictAuthoringModel):
    match: PriorityPolicyMatch
    action: Literal["overridden", "excluded"] = "overridden"
    overridden_by: list[str] = Field(default_factory=list)
    rationale: str | None = None


class PriorityPolicyExclusion(StrictAuthoringModel):
    match: PriorityPolicyMatch
    rationale: str | None = None


class PriorityPolicyDefaults(StrictAuthoringModel):
    conflict_action: ConflictAction = "compatible"
    default_pack_weight: float = 0.5

    @model_validator(mode="after")
    def _enforce_canonical_conflict_default(self) -> PriorityPolicyDefaults:
        if self.conflict_action == "compatible":
            return self
        if self.conflict_action == "reference_only":
            raise ValueError(
                "defaults.conflict_action must stay compatible; use rule entry reviewability: reference_only instead"
            )
        raise ValueError(
            "defaults.conflict_action must stay compatible; use explicit policy overrides/exclusions instead"
        )


class PriorityPolicy(StrictAuthoringModel):
    schema_version: int = 1
    policy_id: str
    language_id: str = "cpp"
    tier_order: list[PriorityTier] = Field(
        default_factory=lambda: ["override", "high", "default", "reference"]
    )
    pack_weights: dict[str, float] = Field(default_factory=dict)
    defaults: PriorityPolicyDefaults = Field(default_factory=PriorityPolicyDefaults)
    tie_breakers: list[str] = Field(
        default_factory=lambda: [
            "explicit_override",
            "higher_tier",
            "higher_pattern_boost",
            "higher_similarity",
            "higher_specificity",
            "higher_base_score",
            "higher_pack_weight",
            "lexical_rule_id",
        ]
    )
    overrides: list[PriorityPolicyOverride] = Field(default_factory=list)
    exclusions: list[PriorityPolicyExclusion] = Field(default_factory=list)

    @model_validator(mode="after")
    def _normalize_tie_breakers(self) -> PriorityPolicy:
        ordered = list(dict.fromkeys(self.tie_breakers))
        promoted_breakers = ["higher_pattern_boost", "higher_similarity"]

        for breaker in promoted_breakers:
            if breaker in ordered:
                ordered.remove(breaker)

        if "higher_tier" in ordered:
            insert_at = ordered.index("higher_tier") + 1
        elif "explicit_override" in ordered:
            insert_at = ordered.index("explicit_override") + 1
        else:
            insert_at = 0

        for breaker in reversed(promoted_breakers):
            ordered.insert(insert_at, breaker)

        self.tie_breakers = ordered
        return self


class RuleRootManifest(StrictAuthoringModel):
    schema_version: int = 1
    language_id: str = "cpp"
    pack_files: list[str] = Field(default_factory=list)
    profile_files: list[str] = Field(default_factory=list)
    policy_files: list[str] = Field(default_factory=list)


class RulePackageCompatibility(StrictAuthoringModel):
    rule_schema_version: int = 1
    min_review_engine_version: str | None = None
    max_review_engine_version: str | None = None
    build_identifier: str | None = None

    @model_validator(mode="after")
    def _enforce_supported_rule_schema(self) -> RulePackageCompatibility:
        if self.rule_schema_version != 1:
            raise ValueError("compatible_review_engine.rule_schema_version must be 1")
        return self


class RulePackageIncludedFiles(StrictAuthoringModel):
    pack_files: list[str] = Field(default_factory=list)
    profile_files: list[str] = Field(default_factory=list)
    policy_files: list[str] = Field(default_factory=list)
    source_manifest_files: list[str] = Field(default_factory=list)


class RulePackageChecksum(StrictAuthoringModel):
    path: str
    sha256: str

    @field_validator("sha256")
    @classmethod
    def _validate_sha256(cls, value: str) -> str:
        if not _SHA256_RE.fullmatch(value):
            raise ValueError("checksum sha256 must be 64 hexadecimal characters")
        return value


class RulePackageProvenance(StrictAuthoringModel):
    builder: str
    source_revision: str
    build_timestamp: str
    checksums: list[RulePackageChecksum] = Field(default_factory=list)


class RulePackageManifest(StrictAuthoringModel):
    schema_version: Literal[1] = 1
    package_id: str
    package_version: str
    package_kind: Literal["review_engine_rule_extension"]
    compatible_review_engine: RulePackageCompatibility
    extension_roots: list[str] = Field(min_length=1, max_length=1)
    included: RulePackageIncludedFiles
    provenance: RulePackageProvenance

    @field_validator("package_id")
    @classmethod
    def _validate_package_id(cls, value: str) -> str:
        if not _PACKAGE_ID_RE.fullmatch(value):
            raise ValueError(
                "package_id must be stable ASCII using letters, digits, dot, underscore, or hyphen"
            )
        return value

    @field_validator("package_version")
    @classmethod
    def _validate_package_version(cls, value: str) -> str:
        if not _SEMVER_RE.fullmatch(value):
            raise ValueError("package_version must be SemVer-compatible")
        return value


class RuleSourceManifestEntry(StrictAuthoringModel):
    rule_source_id: str
    path: str
    pack_targets: list[str] = Field(default_factory=list)
    profile_id: str | None = None
    context_id: str | None = None
    dialect_id: str | None = None


class RuleSourceLanguageManifest(StrictAuthoringModel):
    language_id: str
    sources: list[RuleSourceManifestEntry] = Field(default_factory=list)


class RuleSourceManifest(StrictAuthoringModel):
    schema_version: int = 1
    bundle_id: str
    default_chunking: dict[str, str | int] = Field(default_factory=dict)
    languages: list[RuleSourceLanguageManifest] = Field(default_factory=list)


class ParsedRule(BaseModel):
    rule_no: str
    source: str
    pack_id: str | None = None
    source_kind: str = "public_standard"
    language_id: str = "cpp"
    context_id: str | None = None
    dialect_id: str | None = None
    namespace: str | None = None
    source_family: str | None = None
    section: str
    title: str
    text: str
    summary: str
    keywords: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _sync_pack_and_legacy_source(self) -> ParsedRule:
        self.pack_id, self.source_family = _normalize_pack_identity(
            self.pack_id,
            self.source_family,
        )
        self.namespace = self.namespace or _default_namespace(self.source_kind)
        return self


class GuidelineRecord(ParsedRule):
    id: str | None = None
    rule_uid: str | None = None
    rule_pack: str | None = None
    base_score: float = 0.5
    priority_tier: PriorityTier = "default"
    pack_weight: float = 0.5
    specificity: float = 0.5
    explicit_override: bool = False
    authority: str | None = None
    priority: float | None = None
    severity_default: float = 0.5
    conflict_action: ConflictAction = "compatible"
    conflict_policy: str | None = None
    embedding_text: str | None = None
    overridden_by: list[str] = Field(default_factory=list)
    conflict_reason: str | None = None
    active: bool = True
    reviewability: Reviewability = "auto_review"
    applies_to: list[AppliesTo] = Field(default_factory=lambda: ["code", "diff"])
    category: str = "general"
    false_positive_risk: Literal["low", "medium", "high"] = "medium"
    trigger_patterns: list[str] = Field(default_factory=list)
    bot_comment_template: str | None = None
    fix_guidance: str | None = None
    review_rank_default: float = 0.5
    file_globs: list[str] = Field(default_factory=list)
    symbol_hints: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _sync_runtime_aliases(self) -> GuidelineRecord:
        self.id = self.id or f"{self.pack_id}:{self.rule_no}"
        self.rule_uid = self.rule_uid or self.id
        self.rule_pack = self.rule_pack or self.pack_id
        self.source_family = self.source_family or self.pack_id
        self.authority = self.authority or _legacy_authority(self.source_kind)
        self.priority = self.base_score if self.priority is None else self.priority
        self.conflict_policy = self.conflict_policy or _legacy_conflict_policy(
            self.conflict_action,
            self.priority_tier,
        )
        if self.review_rank_default == 0.5 and self.base_score != 0.5:
            self.review_rank_default = round(self.base_score, 4)
        if not self.embedding_text:
            self.embedding_text = _build_embedding_text(
                rule_no=self.rule_no,
                section=self.section,
                title=self.title,
                summary=self.summary,
                keywords=self.keywords + self.tags,
                category=self.category,
                reviewability=self.reviewability,
                trigger_patterns=self.trigger_patterns,
                fix_guidance=self.fix_guidance,
                text=self.text,
                pack_id=self.pack_id or "unknown",
                language_id=self.language_id,
                context_id=self.context_id,
                dialect_id=self.dialect_id,
            )
        return self

    def chroma_metadata(self) -> dict[str, float | int | str | bool]:
        return {
            "id": self.id or "",
            "rule_uid": self.rule_uid or "",
            "rule_no": self.rule_no,
            "source": self.source,
            "pack_id": self.pack_id or "",
            "rule_pack": self.rule_pack or self.pack_id or "",
            "source_kind": self.source_kind,
            "language_id": self.language_id,
            "context_id": self.context_id or "",
            "dialect_id": self.dialect_id or "",
            "namespace": self.namespace or "",
            "source_family": self.source_family or "",
            "authority": self.authority or "",
            "section": self.section,
            "title": self.title,
            "summary": self.summary,
            "text": self.text,
            "keywords": ",".join(self.keywords),
            "tags": ",".join(self.tags),
            "priority": self.priority if self.priority is not None else self.base_score,
            "base_score": self.base_score,
            "priority_tier": self.priority_tier,
            "pack_weight": self.pack_weight,
            "specificity": self.specificity,
            "explicit_override": self.explicit_override,
            "severity_default": self.severity_default,
            "conflict_policy": self.conflict_policy or "",
            "conflict_action": self.conflict_action,
            "overridden_by": ",".join(self.overridden_by),
            "conflict_reason": self.conflict_reason or "",
            "active": self.active,
            "reviewability": self.reviewability,
            "applies_to": ",".join(self.applies_to),
            "category": self.category,
            "false_positive_risk": self.false_positive_risk,
            "trigger_patterns": ",".join(self.trigger_patterns),
            "bot_comment_template": self.bot_comment_template or "",
            "fix_guidance": self.fix_guidance or "",
            "review_rank_default": self.review_rank_default,
            "file_globs": ",".join(self.file_globs),
            "symbol_hints": ",".join(self.symbol_hints),
        }


class QueryPattern(BaseModel):
    name: str
    description: str
    weight: float
    evidence: list[str] = Field(default_factory=list)


class QueryAnalysis(BaseModel):
    input_kind: Literal["code", "diff"]
    language_id: str = "cpp"
    profile_id: str = "default"
    context_id: str | None = None
    dialect_id: str | None = None
    query_plugin_id: str | None = None
    detector_refs: list[str] = Field(default_factory=list)
    query_text: str
    patterns: list[QueryPattern] = Field(default_factory=list)


class CandidateHit(BaseModel):
    record: GuidelineRecord
    distance: float
    similarity_score: float
    pack_weight_score: float = 0.0
    pattern_boost: float = 0.0
    final_score: float = 0.0


class ReviewResult(BaseModel):
    rule_no: str
    rule_uid: str | None = None
    rule_pack: str | None = None
    source_family: str
    authority: str
    conflict_policy: str
    title: str
    section: str
    priority: float
    score: float
    summary: str
    text: str
    category: str
    reviewability: str
    fix_guidance: str | None = None
    pack_id: str | None = None
    source_kind: str | None = None
    priority_tier: str | None = None
    pack_weight: float | None = None
    language_id: str | None = None
    context_id: str | None = None
    dialect_id: str | None = None
    conflict_action: str | None = None


class ReviewResponse(BaseModel):
    language_id: str = "cpp"
    profile_id: str = "default"
    context_id: str | None = None
    dialect_id: str | None = None
    prompt_overlay_refs: list[str] = Field(default_factory=list)
    query_text: str
    detected_patterns: list[str]
    results: list[ReviewResult]


class ReviewCodeRequest(BaseModel):
    code: str
    top_k: int = 10
    file_path: str | None = None
    file_context: str | None = None
    language_id: str | None = None
    profile_id: str | None = None
    context_id: str | None = None
    dialect_id: str | None = None


class ReviewDiffRequest(BaseModel):
    diff: str
    top_k: int = 10
    file_path: str | None = None
    file_context: str | None = None
    language_id: str | None = None
    profile_id: str | None = None
    context_id: str | None = None
    dialect_id: str | None = None


class IngestionSummary(BaseModel):
    total_parsed: int
    organization_policy_records: int = 0
    cpp_core_records: int = 0
    active_records: int
    reference_records: int = 0
    excluded_records: int
    source_html_cache: str = ""
    active_dataset_path: str
    reference_dataset_path: str | None = None
    excluded_dataset_path: str | None = None
    parsed_cpp_core_path: str = ""
    collections: dict[str, int] = Field(default_factory=dict)
    parsed_pack_counts: dict[str, int] = Field(default_factory=dict)
    public_rule_root: str | None = None
    extension_rule_roots: list[str] = Field(default_factory=list)
    languages: dict[str, dict[str, int | str]] = Field(default_factory=dict)
    dataset_paths: dict[str, dict[str, str]] = Field(default_factory=dict)


class ConflictResolutionResult(BaseModel):
    all_records: list[GuidelineRecord]
    active_records: list[GuidelineRecord]
    reference_records: list[GuidelineRecord] = Field(default_factory=list)
    excluded_records: list[GuidelineRecord]


class RepoFileFinding(BaseModel):
    path: str
    language_id: str | None = None
    profile_id: str | None = None
    context_id: str | None = None
    dialect_id: str | None = None
    score: float
    pattern_count: int
    patterns: list[QueryPattern] = Field(default_factory=list)


class RepoScanReport(BaseModel):
    root: str
    scanned_files: int
    matched_files: int
    aggregate_patterns: dict[str, int] = Field(default_factory=dict)
    findings: list[RepoFileFinding] = Field(default_factory=list)


class LoadedRuleContext(BaseModel):
    language_id: str
    profile: ProfileConfig
    policy: PriorityPolicy
    context_id: str | None = None
    dialect_id: str | None = None
    selected_pack_ids: list[str] = Field(default_factory=list)
    shared_pack_ids: list[str] = Field(default_factory=list)
    active_records: list[GuidelineRecord]
    reference_records: list[GuidelineRecord]
    excluded_records: list[GuidelineRecord]
    parsed_pack_counts: dict[str, int] = Field(default_factory=dict)
    public_rule_root: str | None = None
    extension_rule_roots: list[str] = Field(default_factory=list)
    prompt_overlay_refs: list[str] = Field(default_factory=list)
    detector_refs: list[str] = Field(default_factory=list)


class LanguageRegistryEntry(BaseModel):
    language_id: str
    display_name: str
    query_plugin_id: str
    default_profile: str = "default"
    default_context_id: str | None = None
    default_dialect_id: str | None = None
    file_extensions: list[str] = Field(default_factory=list)
    filenames: list[str] = Field(default_factory=list)
    path_globs: list[str] = Field(default_factory=list)
    shebangs: list[str] = Field(default_factory=list)
    reviewable: bool = True


class LanguageMatch(BaseModel):
    language_id: str
    profile_id: str
    query_plugin_id: str
    reviewable: bool = True
    context_id: str | None = None
    dialect_id: str | None = None
    match_source: str = "default"
