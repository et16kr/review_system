from __future__ import annotations

import logging
from typing import Literal

from openai import OpenAI
from pydantic import BaseModel, Field

from review_bot.config import get_settings
from review_bot.providers.base import FindingDraft, ReviewCommentProvider, VerifyDraftResult
from review_bot.providers.prompting import get_prompt_composer

logger = logging.getLogger(__name__)

_BASE_SYSTEM_FALLBACK = (
    "당신은 공개 C++ 가이드라인을 바탕으로 변경 코드를 검토하는 선임 리뷰어입니다.\n\n"
    "역할:\n"
    "- 변경된 코드에서 실제로 발생한 문제를 정확히 식별한다\n"
    "- 문제가 없거나 불확실하면 should_publish=false로 응답한다\n"
    "- 모든 응답은 자연스러운 한국어로 작성한다\n\n"
    "코멘트 작성 원칙:\n"
    "1. 무엇이 문제인가 — change_snippet에서 실제 코드를 인용해 evidence_snippet에 기록\n"
    "2. 왜 문제인가 — 안정성, 유지보수성, 안전성 관점에서 설명\n"
    "3. 어떻게 고치는가 — 공개 가이드라인과 표준 C++에 맞는 수정 방향 제시\n"
    "4. confidence >= 0.9이고 수정이 확실하면 auto_fix_lines에 수정된 코드 줄을 제공\n\n"
    "금지 사항:\n"
    "- 규칙 ID나 가이드라인 이름 직접 언급 금지\n"
    "- 코드에서 실제로 보이지 않는 문제 언급 금지\n"
    "- 불확실한 내용을 확실한 것처럼 서술 금지\n"
    "- 50자를 초과하는 제목 금지\n"
    "- candidate_line_nos에 없는 라인 번호 사용 금지"
)

_MEMORY_HINT = (
    "\n\n[메모리/수명 관점]\n"
    "- 소유권, 수명, 해제 경로(정상/예외)를 추적하라\n"
    "- malloc/free, raw new/delete, 누수, double-free, use-after-free 가능성을 점검하라\n"
    "- RAII, std::unique_ptr, std::vector 같은 더 안전한 대안을 구체적으로 제시하라"
)

_ERROR_HANDLING_HINT = (
    "\n\n[에러 처리 관점]\n"
    "- 실패 경로에서 자원이 일관되게 정리되는지 확인하라\n"
    "- 조기 반환, goto cleanup, 수동 정리 블록이 오류를 숨기지 않는지 점검하라\n"
    "- 더 구조화된 에러 전파나 cleanup 전략이 있는지 제안하라"
)

_NAMING_HINT = (
    "\n\n[명명/가독성 관점]\n"
    "- 타입, 함수, 변수 이름이 역할과 소유권을 충분히 드러내는지 확인하라\n"
    "- 혼동을 부르는 축약어, 모호한 이름, 맥락 없는 접두어/접미어를 지적하라"
)

_PORTABILITY_HINT = (
    "\n\n[이식성 관점]\n"
    "- 플랫폼 의존적 타입 크기 가정이나 비표준 include 사용을 찾아라\n"
    "- 직접 시스템 API 호출이 portability와 테스트 용이성을 해치지 않는지 살펴보라\n"
    "- 표준 C++ 또는 더 휴대성 높은 추상화로 바꿀 수 있는지 제안하라"
)

_AGENT_HINTS: dict[str, str] = {
    "memory": _MEMORY_HINT,
    "error_handling": _ERROR_HANDLING_HINT,
    "wrapper_usage": (
        "\n\n[캡슐화/추상화 관점]\n"
        "- low-level 호출이 여러 곳에 흩어져 있는지 살펴보라\n"
        "- 더 좁고 안전한 wrapper나 helper로 감쌀 수 있는지 제안하라\n"
        "- 호출자가 내부 제약을 과도하게 알아야 하는 API를 지적하라"
    ),
    "portability": _PORTABILITY_HINT,
    "type_usage": (
        "\n\n[타입 사용 관점]\n"
        "- primitive 타입과 raw pointer가 너무 많은 의미를 동시에 담고 있지 않은지 보라\n"
        "- 더 강한 타입, 소유권 표현, 명확한 인터페이스가 가능한지 제안하라"
    ),
    "control_flow": (
        "\n\n[제어 흐름 관점]\n"
        "- continue, switch, 조기 return, cleanup 분기가 의도를 숨기지 않는지 점검하라\n"
        "- 읽는 사람이 실수하기 쉬운 흐름을 더 명시적인 구조로 바꿀 수 있는지 제안하라"
    ),
    "comment_usage": (
        "\n\n[주석 관점]\n"
        "- 주석이 코드와 충돌하거나 죽은 코드를 설명 없이 감추고 있지 않은지 살펴보라\n"
        "- 코드 자체를 더 명확하게 하거나 오래된 주석을 정리하는 방향을 제안하라"
    ),
    "naming": _NAMING_HINT,
    "format_usage": (
        "\n\n[포맷/I-O 관점]\n"
        "- printf 계열 사용, 형식 문자열, 타입 불일치 가능성을 점검하라\n"
        "- 더 안전하고 typed 된 formatting 또는 I/O 방향이 있는지 제안하라"
    ),
    "memory_management": _MEMORY_HINT,
    "naming_convention": _NAMING_HINT,
    "thread_safety": (
        "\n\n[동시성 안전성 관점]\n"
        "- 잠금 없는 공유 상태 접근, 경쟁 조건, 수동 lock/unlock 짝 불일치를 찾아라\n"
        "- scoped lock 같은 더 안전한 패턴을 제안하라"
    ),
}

_VERIFY_SYSTEM_PROMPT = (
    "주어진 코드 리뷰 코멘트가 실제 코드 변경에 적용되는지만 판단하세요. "
    "JSON으로만 응답하세요. "
    "applies=false인 경우 reason은 "
    "`not_a_real_bug`, `low_confidence`, `pattern_mismatch`, `execution_error` "
    "중 하나만 사용하세요."
)


class ReviewDraftPayload(BaseModel):
    title: str = Field(description="50자 이하 한국어 제목. 규칙 ID 미포함.")
    summary: str = Field(description="문제-이유-해결 구조의 자연스러운 한국어 설명.")
    severity: Literal["low", "medium", "high", "critical"]
    confidence: float = Field(ge=0.0, le=1.0)
    line_no: int | None = None
    suggested_fix: str | None = Field(
        default=None,
        description="수정 방법 한국어 설명. 코드 예시는 ```cpp``` 블록으로 포함.",
    )
    should_publish: bool = True
    evidence_snippet: str | None = Field(
        default=None,
        description="문제가 되는 실제 코드 줄 인용. change_snippet에서 그대로 가져올 것.",
    )
    auto_fix_lines: list[str] = Field(
        default_factory=list,
        description="confidence >= 0.9일 때 수정된 코드 줄 목록. GitLab suggestion 블록으로 게시됨.",
    )


class VerifyPayload(BaseModel):
    applies: bool
    reason: str = Field(
        default="",
        description=(
            "applies=false일 때만 사용. "
            "허용값: not_a_real_bug, low_confidence, pattern_mismatch, execution_error"
        ),
    )
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class OpenAIReviewCommentProvider(ReviewCommentProvider):
    def __init__(self) -> None:
        settings = get_settings()
        self.model = settings.openai_model
        self._max_retries = settings.openai_max_retries
        self._timeout = settings.openai_timeout_seconds
        self._prompt_composer = get_prompt_composer()
        self._client: OpenAI | None = None

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(
                max_retries=self._max_retries,
                timeout=self._timeout,
            )
        return self._client

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
        file_context: str | None = None,
        language_id: str | None = None,
        profile_id: str | None = None,
        prompt_overlay_refs: list[str] | tuple[str, ...] | None = None,
        pr_title: str | None = None,
        pr_source_branch: str | None = None,
        pr_target_branch: str | None = None,
        similar_code: list[dict] | None = None,
    ) -> FindingDraft:
        del rule_no, rule_text
        candidate_line_text = ", ".join(str(n) for n in candidate_line_nos)

        agent_hint = _AGENT_HINTS.get(category or "", "")
        base_prompt = self._prompt_composer.compose(
            language_id=language_id or "cpp",
            profile_id=profile_id or "default",
            overlay_refs=list(prompt_overlay_refs or []),
        )
        system_prompt = (base_prompt or _BASE_SYSTEM_FALLBACK) + agent_hint

        pr_section = ""
        if pr_title or pr_source_branch:
            parts = []
            if pr_title:
                parts.append(f"제목: {pr_title}")
            if pr_source_branch and pr_target_branch:
                parts.append(f"브랜치: {pr_source_branch} → {pr_target_branch}")
            pr_section = "[PR 정보]\n" + "\n".join(parts) + "\n\n"

        context_section = ""
        if file_context:
            truncated = file_context[:3000]
            context_section = f"[파일 컨텍스트 (참고용)]\n{truncated}\n\n"

        similar_section = ""
        if similar_code:
            lines = ["[코드베이스 유사 패턴 (참고용)]"]
            for hit in similar_code[:2]:
                fp = hit.get("file_path", "")
                fn = hit.get("func_name", "")
                snippet = hit.get("snippet", "")[:400]
                lines.append(f"// {fp} — {fn}\n{snippet}")
            similar_section = "\n\n".join(lines) + "\n\n"

        user_content = (
            f"{pr_section}"
            f"{context_section}"
            f"{similar_section}"
            f"[검토 파일]\n"
            f"파일: {file_path}\n"
            f"변경 내용:\n{change_snippet or ''}\n\n"
            f"[적용 규칙]\n"
            f"분류: {category or ''}\n"
            f"문제: {title}\n"
            f"설명: {summary}\n"
            f"수정 지침: {fix_guidance or ''}\n\n"
            f"[위치 정보]\n"
            f"후보 라인 번호: {candidate_line_text}\n"
            f"확정 라인: {line_no if line_no is not None else ''}\n"
        )

        response = self.client.responses.parse(
            model=self.model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
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
            evidence_snippet=payload.evidence_snippet,
            auto_fix_lines=payload.auto_fix_lines if payload.confidence >= 0.9 else [],
        )

    def verify_draft(
        self,
        *,
        draft: FindingDraft,
        file_path: str,
        rule_no: str,
        title: str,
        summary: str,
        category: str | None = None,
        change_snippet: str | None = None,
        line_no: int | None = None,
        candidate_line_nos: tuple[int, ...] = (),
        file_context: str | None = None,
        language_id: str | None = None,
        profile_id: str | None = None,
        prompt_overlay_refs: list[str] | tuple[str, ...] | None = None,
        pr_title: str | None = None,
        pr_source_branch: str | None = None,
        pr_target_branch: str | None = None,
        similar_code: list[dict] | None = None,
    ) -> VerifyDraftResult:
        del file_path, rule_no, title, summary, category, line_no, candidate_line_nos
        del (
            file_context,
            language_id,
            profile_id,
            prompt_overlay_refs,
            pr_title,
            pr_source_branch,
            pr_target_branch,
            similar_code,
        )
        verify_content = (
            f"코드 리뷰 코멘트 제목: {draft.title}\n"
            f"코드 리뷰 코멘트 본문: {draft.summary}\n\n"
            f"실제 코드 변경:\n{(change_snippet or '')[:2000]}\n\n"
            "이 코멘트가 위 코드 변경에 실제로 적용되는가? "
            "코드에 해당 문제가 실제로 존재하는가?"
        )
        response = self.client.responses.parse(
            model=self.model,
            input=[
                {"role": "system", "content": _VERIFY_SYSTEM_PROMPT},
                {"role": "user", "content": verify_content},
            ],
            text_format=VerifyPayload,
        )
        payload = response.output_parsed
        if payload is None:
            raise ValueError("Structured verify output parsing returned no payload.")
        return VerifyDraftResult(
            applies=payload.applies,
            reason=payload.reason,
            confidence=payload.confidence,
        )
