from __future__ import annotations

from typing import Literal

from openai import OpenAI
from pydantic import BaseModel, Field

from review_bot.config import get_settings
from review_bot.providers.base import FindingDraft, ReviewCommentProvider


class ReviewDraftPayload(BaseModel):
    title: str = Field(description="Short Korean review title without rule ids.")
    summary: str = Field(
        description="Natural Korean explanation of what is wrong and why it matters."
    )
    severity: Literal["low", "medium", "high", "critical"]
    confidence: float = Field(ge=0.0, le=1.0)
    line_no: int | None = None
    suggested_fix: str | None = Field(
        default=None,
        description=(
            "Natural Korean repair guidance. "
            "If a concrete example is safe, include a short fenced ```cpp``` code block."
        ),
    )
    should_publish: bool = True


class OpenAIReviewCommentProvider(ReviewCommentProvider):
    def __init__(self) -> None:
        settings = get_settings()
        self.model = settings.openai_model
        self.client = OpenAI(
            max_retries=settings.openai_max_retries,
            timeout=settings.openai_timeout_seconds,
        )

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
        candidate_line_text = ", ".join(str(item) for item in candidate_line_nos)
        response = self.client.responses.parse(
            model=self.model,
            input=[
                {
                    "role": "system",
                    "content": (
                        "You are an internal C++ pull request review bot. "
                        "Return only structured JSON. "
                        "Write natural Korean like a senior reviewer. "
                        "Do not mention rule ids, guideline names, "
                        "source_family, or section names. "
                        "Focus on three things only: what is wrong, "
                        "why it matters, and how to fix it. "
                        "If line_no is set, it must be one of the candidate line numbers. "
                        "If there is no reliable line match, return null for line_no. "
                        "If you can suggest code confidently from the change snippet, "
                        "include a short "
                        "```cpp``` example inside suggested_fix. "
                        "Do not overstate certainty. Keep the tone practical and direct."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"candidate_line_nos: {candidate_line_text}\n"
                        f"file_path: {file_path}\n"
                        f"rule_no: {rule_no}\n"
                        f"title: {title}\n"
                        f"summary: {summary}\n"
                        f"rule_text: {rule_text or ''}\n"
                        f"fix_guidance: {fix_guidance or ''}\n"
                        f"category: {category or ''}\n"
                        f"change_snippet:\n{change_snippet or ''}\n"
                        f"line_no: {line_no if line_no is not None else ''}\n"
                    ),
                },
            ],
            text_format=ReviewDraftPayload,
        )
        payload = response.output_parsed
        if payload is None:
            raise ValueError("Structured output parsing returned no payload.")
        return FindingDraft(
            title=payload.title,
            summary=payload.summary,
            suggested_fix=payload.suggested_fix,
            severity=payload.severity,
            confidence=payload.confidence,
            should_publish=payload.should_publish,
            line_no=payload.line_no,
        )
