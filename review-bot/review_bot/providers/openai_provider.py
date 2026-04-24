from __future__ import annotations

import logging
import re
from typing import Literal

from openai import OpenAI
from pydantic import BaseModel, Field

from review_bot.config import get_settings
from review_bot.providers.base import FindingDraft, ReviewCommentProvider, VerifyDraftResult
from review_bot.providers.prompting import get_prompt_composer

logger = logging.getLogger(__name__)

_BOT_TITLE_PREFIX_RE = re.compile(r"^\s*\[봇 리뷰\]\[[^\]]+\]\s*")
_TITLE_LABEL_RE = re.compile(r"^\s*(제목|title)\s*:\s*", re.IGNORECASE)
_SUMMARY_LABEL_RE = re.compile(r"^\s*(요약|설명|summary|description)\s*:\s*", re.IGNORECASE)
_FIX_LABEL_RE = re.compile(
    r"^\s*(\*\*)?(권장 수정|수정 제안|제안|suggested fix|fix)(\*\*)?\s*:?\s*",
    re.IGNORECASE,
)
_BLOCKQUOTE_RE = re.compile(r"^\s*>+\s?")

_BASE_SYSTEM_FALLBACK = (
    "당신은 공개 멀티 랭귀지 가이드라인을 바탕으로 변경 코드를 검토하는 선임 리뷰어입니다.\n\n"
    "역할:\n"
    "- 변경된 코드에서 실제로 발생한 문제를 정확히 식별한다\n"
    "- 문제가 없거나 불확실하면 should_publish=false로 응답한다\n"
    "- 모든 응답은 자연스러운 한국어로 작성한다\n\n"
    "코멘트 작성 원칙:\n"
    "1. 무엇이 문제인가 — change_snippet에서 실제 코드를 인용해 evidence_snippet에 기록\n"
    "2. 왜 문제인가 — 안정성, 유지보수성, 안전성 관점에서 설명\n"
    "3. 어떻게 고치는가 — 선택된 언어와 프로필에 맞는 수정 방향 제시\n"
    "4. confidence >= 0.9이고 수정이 확실하면 auto_fix_lines에 수정된 코드 줄을 제공\n\n"
    "금지 사항:\n"
    "- 규칙 ID나 가이드라인 이름 직접 언급 금지\n"
    "- 코드에서 실제로 보이지 않는 문제 언급 금지\n"
    "- 불확실한 내용을 확실한 것처럼 서술 금지\n"
    "- 50자를 초과하는 제목 금지\n"
    "- candidate_line_nos에 없는 라인 번호 사용 금지"
)


def _runtime_system_hint(
    *,
    language_id: str | None,
    profile_id: str | None,
    context_id: str | None,
    dialect_id: str | None,
) -> str:
    runtime_parts = [
        f"언어={language_id or 'unknown'}",
        f"프로필={profile_id or 'default'}",
    ]
    if context_id:
        runtime_parts.append(f"컨텍스트={context_id}")
    if dialect_id:
        runtime_parts.append(f"다이얼렉트={dialect_id}")
    return (
        "\n\n[선택된 검토 런타임]\n"
        f"- {' | '.join(runtime_parts)}\n"
        "- 이 조합 바깥의 언어/프레임워크 조언을 섞지 마세요.\n"
        "- 제목은 짧고 직접적으로 쓰고, 언어 태그나 규칙 ID는 제목에 넣지 마세요.\n"
        "- 요약은 실제 변경 코드에 근거한 한 가지 문제만 좁게 설명하세요."
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

_SECURITY_HINT = (
    "\n\n[보안/신뢰 경계 관점]\n"
    "- 외부 입력, 비밀값, 권한, provenance 경계가 어디인지 먼저 특정하라\n"
    "- 입력 검증이 boundary 근처에서 이루어지는지, 우회 경로가 없는지 점검하라\n"
    "- secret 노출, 과도한 권한, 검증 없는 원격 실행 같은 고신뢰 위험을 우선 지적하라"
)

_CONFIGURATION_HINT = (
    "\n\n[설정/구성 관점]\n"
    "- 기본값, merge, pinning, parser 해석 차이로 의미가 흔들리지 않는지 보라\n"
    "- 재현성, drift, 환경별 오해를 부르는 설정을 우선 지적하라\n"
    "- 설정 계약이 문서/운영 기대와 다르게 넓어지지 않는지 확인하라"
)

_PROCESS_HINT = (
    "\n\n[운영/변경 안전성 관점]\n"
    "- 롤아웃, 재실행, 디버깅, 되돌리기 관점에서 설명 가능한 변경인지 보라\n"
    "- 암묵적 계약보다 코드와 설정에 드러난 explicit contract를 선호하라\n"
    "- 리뷰 포인트는 추상 규범보다 실제 변경의 운영 리스크에 맞춰 좁혀라"
)

_SQL_QUALITY_HINT = (
    "\n\n[SQL 품질 관점]\n"
    "- 정렬, grouping, null 처리, window, 중복 의미가 암묵적이지 않은지 확인하라\n"
    "- ordinal 참조나 엔진 의존 동작이 결과 계약을 흔들지 않는지 점검하라\n"
    "- migration/warehouse SQL이면 idempotency, lock 영향, 재실행 안정성도 함께 보라"
)

_API_CONTRACT_HINT = (
    "\n\n[API 계약 관점]\n"
    "- 요청/응답 경계의 타입, schema, validation이 boundary 근처에서 고정되는지 보라\n"
    "- 호출자와 구현체가 서로 다른 계약을 기대하게 만드는 흐름을 지적하라\n"
    "- backward compatibility와 explicit error contract를 우선 고려하라"
)

_RESOURCE_HINT = (
    "\n\n[자원 수명 관점]\n"
    "- 파일, 연결, 세션, 트랜잭션, 스트림의 획득과 해제 경로를 추적하라\n"
    "- 정상/오류/조기 반환 경로에서 정리 책임이 흩어지지 않는지 보라\n"
    "- 수동 close/release보다 더 구조화된 lifetime 관리 방식을 우선 제안하라"
)

_CONCURRENCY_HINT = (
    "\n\n[동시성/비동기 관점]\n"
    "- task/thread/goroutine ownership, cancellation, shared state 경계를 먼저 특정하라\n"
    "- blocking 작업이 async 경로를 막거나 detached 실행이 오류를 숨기지 않는지 점검하라\n"
    "- lock, channel, scheduler 경계에서 재현 어려운 race/leak 가능성을 우선 보라"
)

_PERFORMANCE_HINT = (
    "\n\n[성능/경로 비용 관점]\n"
    "- hot path, request path, loop 내부에서 비용이 증폭되는 연산을 찾으라\n"
    "- N+1, blocking I/O, 불필요한 materialization, wide scan 가능성을 구체적으로 설명하라\n"
    "- 단순 최적화보다 latency/throughput contract를 깨는 구조를 우선 지적하라"
)

_STATE_HINT = (
    "\n\n[상태 관리 관점]\n"
    "- 캐시, 훅 상태, 서버/클라이언트 경계, 재검증 타이밍이 일관적인지 보라\n"
    "- stale capture, 중복 source of truth, invalidation 누락 가능성을 점검하라\n"
    "- 상태 갱신 규칙이 암묵적이지 않도록 더 좁고 명시적인 경계를 제안하라"
)

_CONTAINER_HINT = (
    "\n\n[컨테이너/런타임 관점]\n"
    "- base image provenance, 권한, 런타임 surface, pinning 상태를 먼저 보라\n"
    "- latest tag, 과도한 패키지, root 실행, 원격 다운로드 실행 같은 위험을 우선 지적하라\n"
    "- 빌드 단계와 런타임 단계를 분리할 수 있는지 함께 고려하라"
)

_SCRIPT_HINT = (
    "\n\n[스크립트 안전성 관점]\n"
    "- quoting, globbing, pipefail, error propagation, cleanup idempotency를 점검하라\n"
    "- 환경 차이에서 깨질 수 있는 암묵적 shell 가정을 줄이는 방향을 제안하라\n"
    "- 운영 스크립트라면 재실행 가능성과 실패 시 복구 경로를 우선 보라"
)

_COMMAND_HINT = (
    "\n\n[명령/CLI 계약 관점]\n"
    "- 플래그 의미, 기본 동작, 출력 포맷이 자동화/스크립트 사용에 안전한지 보라\n"
    "- destructive 동작이 충분히 명시되는지, dry-run/confirm 경계가 있는지 점검하라\n"
    "- 사용자가 오해하기 쉬운 기본값이나 숨은 side effect를 우선 지적하라"
)

_AGENT_HINTS: dict[str, str] = {
    "security": _SECURITY_HINT,
    "configuration": _CONFIGURATION_HINT,
    "process": _PROCESS_HINT,
    "sql_quality": _SQL_QUALITY_HINT,
    "api_contract": _API_CONTRACT_HINT,
    "resource_management": _RESOURCE_HINT,
    "concurrency": _CONCURRENCY_HINT,
    "performance": _PERFORMANCE_HINT,
    "ownership": _MEMORY_HINT,
    "state_management": _STATE_HINT,
    "container_hygiene": _CONTAINER_HINT,
    "script_safety": _SCRIPT_HINT,
    "command_design": _COMMAND_HINT,
    "abstraction": (
        "\n\n[추상화/경계 관점]\n"
        "- low-level 세부사항이 호출자에게 과도하게 새지 않는지 보라\n"
        "- 더 좁고 안정적인 helper, facade, wrapper로 계약을 정리할 수 있는지 제안하라\n"
        "- 구현 세부사항 의존이 호출자 코드에 퍼지는 지점을 우선 지적하라"
    ),
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
        description="수정 방법 한국어 설명. 코드 예시는 해당 언어 fenced code block으로 포함.",
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


def _normalize_multiline_text(value: str | None) -> str:
    if not value:
        return ""
    normalized = value.replace("\r\n", "\n").replace("\r", "\n").strip()
    return re.sub(r"\n{3,}", "\n\n", normalized)


def _normalize_title(value: str | None, *, fallback: str) -> str:
    normalized = _normalize_multiline_text(value) or fallback
    normalized = normalized.splitlines()[0].strip()
    normalized = _BOT_TITLE_PREFIX_RE.sub("", normalized)
    normalized = _TITLE_LABEL_RE.sub("", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip("`'\"[]() ")
    if not normalized:
        normalized = fallback.strip()
    if len(normalized) > 50:
        normalized = normalized[:47].rstrip() + "..."
    return normalized


def _normalize_summary(value: str | None, *, fallback: str) -> str:
    normalized = _normalize_multiline_text(value) or fallback
    normalized = _SUMMARY_LABEL_RE.sub("", normalized, count=1)
    return normalized.strip() or fallback


def _normalize_suggested_fix(value: str | None) -> str | None:
    normalized = _normalize_multiline_text(value)
    if not normalized:
        return None
    normalized = _FIX_LABEL_RE.sub("", normalized, count=1)
    return normalized.strip() or None


def _normalize_evidence_snippet(value: str | None) -> str | None:
    normalized = _normalize_multiline_text(value)
    if not normalized:
        return None
    lines = [_BLOCKQUOTE_RE.sub("", line).rstrip() for line in normalized.splitlines()]
    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    normalized = "\n".join(lines).strip()
    return normalized or None


class OpenAIReviewCommentProvider(ReviewCommentProvider):
    provider_name = "openai"

    def __init__(self) -> None:
        settings = get_settings()
        self.model = settings.openai_model
        self.base_url = settings.openai_base_url
        self._max_retries = settings.openai_max_retries
        self._timeout = settings.openai_timeout_seconds
        self._prompt_composer = get_prompt_composer()
        self._client: OpenAI | None = None

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(
                base_url=self.base_url,
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
        context_id: str | None = None,
        dialect_id: str | None = None,
        prompt_overlay_refs: list[str] | tuple[str, ...] | None = None,
        pr_title: str | None = None,
        pr_source_branch: str | None = None,
        pr_target_branch: str | None = None,
        similar_code: list[dict] | None = None,
    ) -> FindingDraft:
        del rule_no, rule_text
        candidate_line_text = ", ".join(str(n) for n in candidate_line_nos)

        agent_hint = _AGENT_HINTS.get(category or "", "")
        try:
            base_prompt = self._prompt_composer.compose(
                language_id=language_id,
                profile_id=profile_id or "default",
                context_id=context_id,
                overlay_refs=list(prompt_overlay_refs or []),
            )
        except TypeError:
            base_prompt = self._prompt_composer.compose(
                language_id=language_id,
                profile_id=profile_id or "default",
                overlay_refs=list(prompt_overlay_refs or []),
            )
        system_prompt = (
            (base_prompt or _BASE_SYSTEM_FALLBACK)
            + _runtime_system_hint(
                language_id=language_id,
                profile_id=profile_id,
                context_id=context_id,
                dialect_id=dialect_id,
            )
            + agent_hint
        )

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
            f"언어: {language_id or ''}\n"
            f"프로필: {profile_id or ''}\n"
            f"컨텍스트: {context_id or ''}\n"
            f"다이얼렉트: {dialect_id or ''}\n"
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
            title=_normalize_title(payload.title, fallback=title),
            summary=_normalize_summary(payload.summary, fallback=summary),
            suggested_fix=_normalize_suggested_fix(payload.suggested_fix),
            severity=payload.severity,
            confidence=payload.confidence,
            should_publish=payload.should_publish,
            line_no=payload.line_no,
            evidence_snippet=_normalize_evidence_snippet(payload.evidence_snippet),
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
        context_id: str | None = None,
        dialect_id: str | None = None,
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
            context_id,
            dialect_id,
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
