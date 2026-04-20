from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ParsedRule(BaseModel):
    rule_no: str
    source: str
    source_family: Literal["altibase", "cpp_core"]
    section: str
    title: str
    text: str
    summary: str
    keywords: list[str] = Field(default_factory=list)


class GuidelineRecord(ParsedRule):
    id: str
    authority: Literal["internal", "external"]
    priority: float
    severity_default: float
    conflict_policy: Literal["authoritative", "compatible", "overridden", "excluded"]
    embedding_text: str
    overridden_by: list[str] = Field(default_factory=list)
    conflict_reason: str | None = None
    active: bool = True
    reviewability: Literal["auto_review", "manual_only", "reference_only"] = "auto_review"
    applies_to: list[str] = Field(default_factory=lambda: ["code", "diff"])
    category: str = "general"
    false_positive_risk: Literal["low", "medium", "high"] = "medium"
    trigger_patterns: list[str] = Field(default_factory=list)
    bot_comment_template: str | None = None
    fix_guidance: str | None = None
    review_rank_default: float = 0.5

    def chroma_metadata(self) -> dict[str, float | int | str | bool]:
        return {
            "rule_no": self.rule_no,
            "source": self.source,
            "source_family": self.source_family,
            "authority": self.authority,
            "section": self.section,
            "title": self.title,
            "summary": self.summary,
            "text": self.text,
            "keywords": ",".join(self.keywords),
            "priority": self.priority,
            "severity_default": self.severity_default,
            "conflict_policy": self.conflict_policy,
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
        }


class QueryPattern(BaseModel):
    name: str
    description: str
    weight: float
    evidence: list[str] = Field(default_factory=list)


class QueryAnalysis(BaseModel):
    input_kind: Literal["code", "diff"]
    query_text: str
    patterns: list[QueryPattern] = Field(default_factory=list)


class CandidateHit(BaseModel):
    record: GuidelineRecord
    distance: float
    similarity_score: float
    authority_score: float = 0.0
    pattern_boost: float = 0.0
    final_score: float = 0.0


class ReviewResult(BaseModel):
    rule_no: str
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


class ReviewResponse(BaseModel):
    query_text: str
    detected_patterns: list[str]
    results: list[ReviewResult]


class ReviewCodeRequest(BaseModel):
    code: str
    top_k: int = 10


class ReviewDiffRequest(BaseModel):
    diff: str
    top_k: int = 10
    file_path: str | None = None
    file_context: str | None = None


class IngestionSummary(BaseModel):
    total_parsed: int
    altibase_records: int
    cpp_core_records: int
    active_records: int
    reference_records: int = 0
    excluded_records: int
    source_html_cache: str
    active_dataset_path: str
    reference_dataset_path: str | None = None
    excluded_dataset_path: str | None = None
    parsed_altibase_path: str
    parsed_cpp_core_path: str
    collections: dict[str, int] = Field(default_factory=dict)


class ConflictResolutionResult(BaseModel):
    all_records: list[GuidelineRecord]
    active_records: list[GuidelineRecord]
    reference_records: list[GuidelineRecord] = Field(default_factory=list)
    excluded_records: list[GuidelineRecord]


class RepoFileFinding(BaseModel):
    path: str
    score: float
    pattern_count: int
    patterns: list[QueryPattern] = Field(default_factory=list)


class RepoScanReport(BaseModel):
    root: str
    scanned_files: int
    matched_files: int
    aggregate_patterns: dict[str, int] = Field(default_factory=dict)
    findings: list[RepoFileFinding] = Field(default_factory=list)
