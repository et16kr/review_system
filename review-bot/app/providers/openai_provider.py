from __future__ import annotations

from typing import Literal

from openai import OpenAI
from pydantic import BaseModel, Field

from app.config import get_settings
from app.providers.base import FindingDraft, ReviewCommentProvider


class ReviewDraftPayload(BaseModel):
    title: str = Field(description="Short Korean review title.")
    summary: str = Field(description="Short Korean review explanation.")
    severity: Literal["low", "medium", "high", "critical"]
    confidence: float = Field(ge=0.0, le=1.0)
    rule_no: str
    line_no: int | None = None
    suggested_fix: str | None = None
    should_publish: bool = True


class OpenAIReviewCommentProvider(ReviewCommentProvider):
    def __init__(self) -> None:
        settings = get_settings()
        self.model = settings.openai_model
        self.client = OpenAI()

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
        line_no: int | None = None,
    ) -> FindingDraft:
        response = self.client.responses.parse(
            model=self.model,
            input=[
                {
                    "role": "system",
                    "content": (
                        "You are an internal C++ pull request review bot. "
                        "Return only structured JSON. Keep every field concise and practical. "
                        "Use Korean for title, summary, and suggested_fix."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"file_path: {file_path}\n"
                        f"rule_no: {rule_no}\n"
                        f"title: {title}\n"
                        f"summary: {summary}\n"
                        f"rule_text: {rule_text or ''}\n"
                        f"fix_guidance: {fix_guidance or ''}\n"
                        f"category: {category or ''}\n"
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
