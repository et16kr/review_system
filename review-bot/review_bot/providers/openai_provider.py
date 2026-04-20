from __future__ import annotations

import logging
from typing import Literal

from openai import OpenAI
from pydantic import BaseModel, Field

from review_bot.config import get_settings
from review_bot.providers.base import FindingDraft, ReviewCommentProvider

logger = logging.getLogger(__name__)

_MEMORY_HINT = (
    "\n\n[메모리 안전성 전문가 관점]\n"
    "- 소유권, 수명, 해제 경로(정상/예외)를 추적하라\n"
    "- malloc/free 쌍의 불일치, double-free, use-after-free 위험을 찾아라\n"
    "- RAII, std::unique_ptr, std::vector 등의 대안을 구체적으로 제시하라"
)

_ERROR_HANDLING_HINT = (
    "\n\n[에러 처리 전문가 관점]\n"
    "- IDE_RC 반환값 체크 누락, IDE_TEST/IDE_ERROR 패턴 위반을 찾아라\n"
    "- 실패 경로에서 자원이 올바르게 해제되는지 확인하라\n"
    "- Altibase IDE_ 매크로 패턴과의 일관성을 검토하라"
)

_NAMING_HINT = (
    "\n\n[명명 규칙 전문가 관점]\n"
    "- Altibase 변수/함수/클래스 명명 패턴을 기준으로 평가하라\n"
    "- 헝가리안 표기법, 접두사 규칙 등 내부 컨벤션 준수를 확인하라"
)

_PORTABILITY_HINT = (
    "\n\n[이식성 전문가 관점]\n"
    "- 플랫폼 의존적 타입(int, long)의 크기 가정을 찾아라\n"
    "- 직접 libc 호출, 컴파일러 확장 사용을 찾아라\n"
    "- 크로스 플랫폼 빌드에서 발생할 수 있는 문제를 예측하라"
)

_SYSTEM_PROMPT = (
    "당신은 Altibase C++ 코드베이스의 선임 리뷰어입니다.\n\n"
    "역할:\n"
    "- 변경된 코드에서 실제로 발생한 문제를 정확히 식별한다\n"
    "- 문제가 없거나 불확실하면 should_publish=false로 응답한다\n"
    "- 모든 응답은 자연스러운 한국어로 작성한다\n\n"
    "코멘트 작성 원칙:\n"
    "1. 무엇이 문제인가 — change_snippet에서 실제 코드를 인용해 evidence_snippet에 기록\n"
    "2. 왜 문제인가 (Altibase 코드베이스에서의 위험성)\n"
    "3. 어떻게 고치는가 (Altibase 코딩 스타일에 맞는 수정 방법)\n"
    "4. confidence >= 0.9이고 수정이 확실하면 auto_fix_lines에 수정된 코드 줄을 제공\n\n"
    "evidence_snippet 작성법:\n"
    "- change_snippet에서 문제가 되는 정확한 코드 줄을 그대로 인용\n"
    "- 형식: `{problematic_code}` 형태의 백틱 인용\n"
    "- 코드에 실제로 있는 내용만 인용할 것\n\n"
    "금지 사항:\n"
    "- 규칙 ID나 가이드라인 이름 직접 언급 금지\n"
    "- 코드에서 실제로 보이지 않는 문제 언급 금지\n"
    "- 불확실한 내용을 확실한 것처럼 서술 금지\n"
    "- 50자를 초과하는 제목 금지\n"
    "- candidate_line_nos에 없는 라인 번호 사용 금지"
)

# 카테고리별 특화 추가 지침 (engine의 실제 category 이름 기준)
_AGENT_HINTS: dict[str, str] = {
    "memory": _MEMORY_HINT,
    "error_handling": _ERROR_HANDLING_HINT,
    "wrapper_usage": (
        "\n\n[내부 래퍼 사용 전문가 관점]\n"
        "- 직접 시스템 호출, libc 호출, 수동 잠금 제어를 우선 의심하라\n"
        "- 승인된 내부 wrapper/API로 치환할 수 있는지 제안하라\n"
        "- 플랫폼 추상화와 운영 일관성을 해치는 우회 호출을 지적하라"
    ),
    "portability": _PORTABILITY_HINT,
    "type_usage": (
        "\n\n[타입 사용 전문가 관점]\n"
        "- Altibase typedef/alias 대신 primitive 타입을 직접 쓰는지 확인하라\n"
        "- 폭이 불명확한 정수형, 캐스팅, ABI 민감 타입 사용을 점검하라\n"
        "- 이식성과 일관성을 위해 내부 타입 체계를 따르도록 제안하라"
    ),
    "control_flow": (
        "\n\n[제어 흐름 전문가 관점]\n"
        "- continue, switch, 조기 return 등으로 의도가 숨겨지는지 살펴보라\n"
        "- 분기 조건과 종료 경로가 읽기 쉽고 안전한지 확인하라\n"
        "- 유지보수 시 실수하기 쉬운 흐름 축약을 명시적 구조로 바꾸도록 제안하라"
    ),
    "comment_usage": (
        "\n\n[주석 규칙 전문가 관점]\n"
        "- 주석 형식이 내부 규칙에 맞는지 확인하라\n"
        "- 주석 처리된 죽은 코드나 오래된 설명이 남아 있는지 찾아라\n"
        "- 코드와 주석이 충돌하면 주석을 정리하거나 제거하도록 제안하라"
    ),
    "naming": _NAMING_HINT,
    "format_usage": (
        "\n\n[포맷 사용 전문가 관점]\n"
        "- printf/format specifier가 타입과 일치하는지 확인하라\n"
        "- portable format macro를 써야 하는 경로인지 검토하라\n"
        "- 표현식 확장이나 로그 포맷이 플랫폼별로 깨질 가능성을 점검하라"
    ),
    # Legacy aliases kept for compatibility with older stored/test fixtures.
    "memory_management": _MEMORY_HINT,
    "naming_convention": _NAMING_HINT,
    "thread_safety": (
        "\n\n[동시성 안전성 전문가 관점]\n"
        "- 잠금 없는 공유 상태 접근, 경쟁 조건 가능성을 찾아라\n"
        "- mutex, atomic, 잠금 순서 문제를 검토하라"
    ),
}

_VERIFY_SYSTEM_PROMPT = (
    "주어진 코드 리뷰 코멘트가 실제 코드 변경에 적용되는지만 판단하세요. "
    "JSON으로만 응답하세요."
)


class ReviewDraftPayload(BaseModel):
    title: str = Field(description="50자 이하 한국어 제목. 규칙 ID 미포함.")
    summary: str = Field(
        description="문제-이유-해결 구조의 자연스러운 한국어 설명."
    )
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
    reason: str = ""


class OpenAIReviewCommentProvider(ReviewCommentProvider):
    def __init__(self) -> None:
        settings = get_settings()
        self.model = settings.openai_model
        self._max_retries = settings.openai_max_retries
        self._timeout = settings.openai_timeout_seconds
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
        pr_title: str | None = None,
        pr_source_branch: str | None = None,
        pr_target_branch: str | None = None,
        similar_code: list[dict] | None = None,
    ) -> FindingDraft:
        candidate_line_text = ", ".join(str(n) for n in candidate_line_nos)

        # 카테고리별 특화 시스템 프롬프트
        agent_hint = _AGENT_HINTS.get(category or "", "")
        system_prompt = _SYSTEM_PROMPT + agent_hint

        # PR 정보 섹션
        pr_section = ""
        if pr_title or pr_source_branch:
            parts = []
            if pr_title:
                parts.append(f"제목: {pr_title}")
            if pr_source_branch and pr_target_branch:
                parts.append(f"브랜치: {pr_source_branch} → {pr_target_branch}")
            pr_section = "[PR 정보]\n" + "\n".join(parts) + "\n\n"

        # 파일 컨텍스트 섹션 (앞 3000자로 제한)
        context_section = ""
        if file_context:
            truncated = file_context[:3000]
            context_section = f"[파일 컨텍스트 (참고용)]\n{truncated}\n\n"

        # RAG 유사 코드 섹션
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

        draft = FindingDraft(
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

        # 자가 검증: 신뢰도가 중간 범위인 경우 LLM으로 주장 재확인
        if draft.should_publish and 0.50 <= draft.confidence < 0.75:
            draft = self._verify_draft(draft, change_snippet or "")

        return draft

    def _verify_draft(self, draft: FindingDraft, snippet: str) -> FindingDraft:
        """LLM 코멘트 주장이 실제 코드 변경에 근거하는지 검증한다."""
        try:
            verify_content = (
                f"코드 리뷰 코멘트: {draft.summary}\n\n"
                f"실제 코드 변경:\n{snippet[:2000]}\n\n"
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
            result = response.output_parsed
            if result is not None and not result.applies:
                logger.info(
                    "verify_rejected title=%r reason=%r confidence=%.2f",
                    draft.title,
                    result.reason,
                    draft.confidence,
                )
                draft.should_publish = False
                draft.confidence = max(0.0, draft.confidence - 0.25)
        except Exception as exc:
            logger.warning("verify_draft_failed error=%s", exc)
        return draft
