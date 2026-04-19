from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass
class FindingDraft:
    title: str
    summary: str
    suggested_fix: str | None
    severity: Literal["low", "medium", "high", "critical"] = "medium"
    confidence: float = 0.7
    should_publish: bool = True
    line_no: int | None = None


class ReviewCommentProvider:
    def build_draft(
        self,
        *,
        file_path: str,
        rule_no: str,
        title: str,
        summary: str,
        rule_text: str | None = None,
        fix_guidance: str | None = None,
        category: str | None = None,
        change_snippet: str | None = None,
        line_no: int | None = None,
        candidate_line_nos: tuple[int, ...] = (),
    ) -> FindingDraft:
        raise NotImplementedError
