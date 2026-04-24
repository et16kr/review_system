from __future__ import annotations

import re

from review_bot.providers.base import FindingDraft, ReviewCommentProvider, VerifyDraftResult
from review_bot.providers.change_analysis import (
    classify_issue,
    extract_changed_excerpt,
    parse_numbered_change_snippet,
    requires_direct_signal,
    select_candidate_line,
)


class StubReviewCommentProvider(ReviewCommentProvider):
    provider_name = "stub"
    transport_class = "deterministic_stub"

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
        del (
            rule_no,
            file_context,
            profile_id,
            context_id,
            dialect_id,
            prompt_overlay_refs,
            pr_title,
            pr_source_branch,
            pr_target_branch,
            similar_code,
        )

        excerpt = extract_changed_excerpt(change_snippet or "")
        issue = classify_issue(excerpt, category, title, summary)
        selected_line_no = select_candidate_line(
            change_snippet=change_snippet or "",
            candidate_line_nos=candidate_line_nos,
            issue=issue,
        )
        draft = _build_guideline_backed_draft(
            language_id=language_id,
            file_path=file_path,
            excerpt=excerpt,
            category=category,
            fallback_title=title,
            fallback_summary=summary,
            rule_text=rule_text,
            fix_guidance=fix_guidance,
        )
        if draft is None:
            draft = _build_issue_draft(
                issue=issue,
                file_path=file_path,
                excerpt=_excerpt_near_selected_line(change_snippet or "", selected_line_no) or excerpt,
                fallback_title=title,
                fallback_summary=summary,
                fix_guidance=fix_guidance,
            )
        draft.line_no = selected_line_no
        if draft.line_no is None and not requires_direct_signal(issue):
            draft.line_no = line_no
        return draft

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
        del (
            file_path,
            rule_no,
            title,
            summary,
            category,
            change_snippet,
            line_no,
            candidate_line_nos,
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
        return VerifyDraftResult(applies=True, confidence=draft.confidence)


def _build_issue_draft(
    *,
    issue: str,
    file_path: str,
    excerpt: str,
    fallback_title: str,
    fallback_summary: str,
    fix_guidance: str | None,
) -> FindingDraft:
    excerpt_hint = _format_excerpt_hint(excerpt)
    normalized_summary = _normalize_summary(fallback_summary, fallback_title)
    cleaned_fix_guidance = _clean_fix_guidance(fix_guidance)

    if issue == "malloc_free":
        return FindingDraft(
            title="메모리를 직접 할당하고 해제하고 있습니다",
            summary=(
                "이 변경에서는 `malloc/free` 또는 그에 준하는 래퍼 호출로 "
                "버퍼 수명을 직접 관리하고 있습니다. "
                "이 방식은 분기 추가나 중간 반환이 생길 때 "
                "해제 누락과 소유권 혼동으로 이어지기 쉽습니다."
                f"{excerpt_hint}"
            ),
            suggested_fix=(
                "버퍼 수명은 객체에 묶어 두고, 가능한 경우 `std::vector`, "
                "전용 owner 구조체, 또는 프로젝트 표준 버퍼 래퍼로 바꿔 주세요. "
                "해제가 꼭 필요하다면 cleanup 경로를 한 곳으로 모으는 편이 안전합니다.\n\n"
                "예시:\n"
                "```cpp\n"
                "std::vector<UChar> wrapped_keys(required_size);\n"
                "fill_keys(wrapped_keys.data(), wrapped_keys.size());\n"
                "use_keys(wrapped_keys.data(), wrapped_keys.size());\n"
                "```"
            ),
            severity="high",
            confidence=0.84,
        )

    if issue == "raw_new_delete":
        return FindingDraft(
            title="동적 객체 수명을 직접 관리하고 있습니다",
            summary=(
                "이 변경은 `new/delete`로 객체 생명주기를 직접 다룹니다. "
                "이 패턴은 소유권이 분산되기 쉬워서 "
                "예외나 조기 반환이 들어오면 누수 가능성이 커집니다."
                f"{excerpt_hint}"
            ),
            suggested_fix=(
                "소유권을 객체에 묶어 두고, 필요한 경우 스마트 포인터나 "
                "프로젝트 표준 owner wrapper로 감싸 주세요.\n\n"
                "예시:\n"
                "```cpp\n"
                "auto item = std::make_unique<MyType>();\n"
                "use(*item);\n"
                "```"
            ),
            severity="high",
            confidence=0.82,
        )

    if issue == "continue_usage":
        return FindingDraft(
            title="루프 흐름이 `continue`에 의존하고 있습니다",
            summary=(
                "`continue`가 들어오면 정상 경로와 예외 경로가 흩어져서 읽기 어려워집니다. "
                "조건을 반대로 세우고 처리 본문을 감싸면 흐름이 더 분명해집니다."
                f"{excerpt_hint}"
            ),
            suggested_fix=(
                "건너뛰는 조건을 먼저 검사하지 말고, 처리할 조건을 `if`로 감싸서 "
                "본문이 한눈에 보이게 바꿔 주세요.\n\n"
                "예시:\n"
                "```cpp\n"
                "if (should_process(item)) {\n"
                "    process(item);\n"
                "}\n"
                "```"
            ),
            severity="medium",
            confidence=0.8,
        )

    if issue == "switch_without_default":
        return FindingDraft(
            title="`switch`에 예외 입력을 처리하는 분기가 없습니다",
            summary=(
                "현재 변경에는 `default` 분기가 보이지 않습니다. "
                "새 enum 값이나 예상 밖 입력이 들어왔을 때 조용히 빠져나가면 "
                "원인 추적이 어려워집니다."
                f"{excerpt_hint}"
            ),
            suggested_fix=(
                "예상하지 못한 값에 대한 기본 분기를 추가해서 "
                "오류 처리나 방어 로직을 분명히 남겨 주세요.\n\n"
                "예시:\n"
                "```cpp\n"
                "switch (state) {\n"
                "case kReady:\n"
                "    handle_ready();\n"
                "    break;\n"
                "default:\n"
                "    rc = IDE_FAILURE;\n"
                "    break;\n"
                "}\n"
                "```"
            ),
            severity="medium",
            confidence=0.81,
        )

    if issue == "ide_assert":
        return FindingDraft(
            title="오류 경로를 `IDE_ASSERT`에만 기대고 있습니다",
            summary=(
                "`IDE_ASSERT`는 개발 중 검증에는 도움이 되지만, "
                "운영 경로의 실패 처리까지 대신해 주지는 못합니다. "
                "실패 가능한 조건이라면 호출자에게 오류를 전달하는 경로가 분명해야 합니다."
                f"{excerpt_hint}"
            ),
            suggested_fix=(
                "검증 실패가 실제 오류가 될 수 있다면 `IDE_TEST` 또는 `IDE_ERROR` 계열로 바꾸고, "
                "호출자가 복구 또는 종료 판단을 할 수 있게 해 주세요."
            ),
            severity="high",
            confidence=0.79,
        )

    if issue == "ide_rc_flow":
        return FindingDraft(
            title="실패 경로의 반환 규약이 더 분명하면 좋겠습니다",
            summary=(
                "이 변경은 실패 가능한 작업을 포함하는데, 반환 경로가 한눈에 드러나지 않습니다. "
                "호출자가 일관되게 처리할 수 있도록 성공/실패 반환 규약을 "
                "분명히 두는 편이 안전합니다."
                f"{excerpt_hint}"
            ),
            suggested_fix=(
                "실패 가능한 함수는 `IDE_RC` 기반으로 정리하고, "
                "cleanup과 반환이 한 곳에서 끝나도록 맞춰 주세요.\n\n"
                "예시:\n"
                "```cpp\n"
                "IDE_RC doWork(...) {\n"
                "    IDE_RC rc = IDE_SUCCESS;\n"
                "    // ...\n"
                "    return rc;\n"
                "}\n"
                "```"
            ),
            severity="medium",
            confidence=0.74,
            should_publish=False,
        )

    if issue == "ide_exception_flow":
        return FindingDraft(
            title="예외 처리 매크로 사용 순서를 더 일관되게 맞춰 주세요",
            summary=(
                "예외/오류 처리 매크로가 섞이면 cleanup 순서와 "
                "오류 전파 경로를 추적하기 어려워집니다. "
                "실패 지점과 종료 지점을 같은 패턴으로 맞추는 편이 유지보수에 유리합니다."
                f"{excerpt_hint}"
            ),
            suggested_fix=(
                "실패 검사, 점프, cleanup, 반환의 순서를 한 패턴으로 통일해 주세요. "
                + (
                    f"현재 팀 기준에서는 다음 방향을 권장합니다: {cleaned_fix_guidance}"
                    if cleaned_fix_guidance
                    else ""
                )
            ),
            severity="medium",
            confidence=0.76,
            should_publish=False,
        )

    if issue == "direct_libc_or_format":
        return FindingDraft(
            title="직접 호출한 라이브러리 함수가 컨벤션을 우회할 수 있습니다",
            summary=(
                "직접 `libc`나 기본 포맷 함수를 호출하면 "
                "타입/이식성/오류 처리 규약이 코드마다 달라지기 쉽습니다. "
                "이 프로젝트에서는 공용 wrapper나 안전한 출력 경로를 쓰는 쪽이 더 안정적입니다."
                f"{excerpt_hint}"
            ),
            suggested_fix=(
                "프로젝트 표준 wrapper가 있다면 그 API로 교체하고, "
                "없더라도 한 곳에서 감싼 뒤 그 래퍼를 호출해 주세요."
            ),
            severity="medium",
            confidence=0.77,
        )

    if issue == "portability":
        return FindingDraft(
            title="플랫폼 의존 요소가 직접 드러나고 있습니다",
            summary=(
                "운영체제 헤더나 시스템 API를 직접 끌어오면 플랫폼별 조건 분기가 빠르게 퍼집니다. "
                "이식성 계층을 한 곳에 두고 사용하는 편이 이후 유지보수에 유리합니다."
                f"{excerpt_hint}"
            ),
            suggested_fix=(
                "플랫폼 종속 include와 호출은 전용 wrapper 또는 "
                "portability 계층으로 밀어 넣어 주세요."
            ),
            severity="medium",
            confidence=0.72,
        )

    if issue == "memory_generic":
        return FindingDraft(
            title="메모리 수명 관리가 더 분명해야 합니다",
            summary=(
                "이 변경은 메모리 소유권과 해제 책임이 분명하지 않아 보입니다. "
                "이 지점은 추후 수정에서 누수나 이중 해제로 이어지기 쉬운 구간입니다."
                f"{excerpt_hint}"
            ),
            suggested_fix=cleaned_fix_guidance
            or (
                "소유권을 한 곳으로 모으고, 수동 해제 대신 "
                "객체 수명에 맡겨 주세요."
            ),
            severity="high",
            confidence=0.74,
            should_publish=False,
        )

    if issue == "control_flow_generic":
        return FindingDraft(
            title="흐름이 한 번에 읽히도록 정리해 주세요",
            summary=(
                "현재 분기 흐름은 예외 경로와 정상 경로가 조금 섞여 있습니다. "
                "조건을 단순하게 정리하면 코드 의도를 더 빨리 파악할 수 있습니다."
                f"{excerpt_hint}"
            ),
            suggested_fix=cleaned_fix_guidance
            or "분기 수를 줄이고, 예외 경로를 명시적으로 드러내 주세요.",
            severity="medium",
            confidence=0.7,
            should_publish=False,
        )

    if issue == "error_handling_generic":
        return FindingDraft(
            title="오류 처리 경로를 더 명확하게 맞춰 주세요",
            summary=(
                "이 변경은 오류 전파 방식이 분명하게 읽히지 않습니다. "
                "실패 시점, cleanup, 반환값이 같은 패턴으로 정리되면 추적이 쉬워집니다."
                f"{excerpt_hint}"
            ),
            suggested_fix=cleaned_fix_guidance
            or "실패 검사와 반환 경로를 일관된 패턴으로 통일해 주세요.",
            severity="medium",
            confidence=0.71,
            should_publish=False,
        )

    if issue == "wrapper_usage_generic":
        return FindingDraft(
            title="직접 호출보다 공용 wrapper를 우선해 주세요",
            summary=(
                "이 변경은 시스템 또는 라이브러리 기능을 바로 사용하는 쪽에 가깝습니다. "
                "공용 wrapper를 거치면 이식성과 로깅, 오류 처리 정책을 같이 가져갈 수 있습니다."
                f"{excerpt_hint}"
            ),
            suggested_fix=cleaned_fix_guidance
            or "프로젝트 표준 wrapper API가 있다면 그 경로로 바꿔 주세요.",
            severity="medium",
            confidence=0.72,
            should_publish=False,
        )

    if issue == "format_usage_generic":
        return FindingDraft(
            title="출력 포맷을 더 안전한 방식으로 맞춰 주세요",
            summary=(
                "기본 format specifier를 직접 사용하면 "
                "타입 크기와 플랫폼 차이에서 문제가 생길 수 있습니다. "
                "안전한 포맷 래퍼나 표준 매크로를 통일해서 쓰는 편이 좋습니다."
                f"{excerpt_hint}"
            ),
            suggested_fix=cleaned_fix_guidance
            or "포맷 문자열은 프로젝트 표준 매크로나 wrapper로 통일해 주세요.",
            severity="medium",
            confidence=0.7,
            should_publish=False,
        )

    return FindingDraft(
        title=_normalize_title(fallback_title),
        summary=(
            "이 변경은 현재 코드베이스의 리뷰 기준과 맞지 않을 가능성이 있습니다. "
            f"{normalized_summary or '문제 지점을 더 직접적으로 정리해 주는 편이 좋겠습니다.'}"
            f"{excerpt_hint}"
        ),
        suggested_fix=cleaned_fix_guidance
        or (
            "무엇이 실패할 수 있는지와 어떻게 정리할지를 "
            "코드에 더 직접적으로 드러내 주세요."
        ),
        severity="medium",
        confidence=0.66,
        should_publish=False,
    )


def _build_guideline_backed_draft(
    *,
    language_id: str | None,
    file_path: str,
    excerpt: str,
    category: str | None,
    fallback_title: str,
    fallback_summary: str,
    rule_text: str | None,
    fix_guidance: str | None,
) -> FindingDraft | None:
    cleaned_fix_guidance = _clean_fix_guidance(fix_guidance)
    excerpt_hint = _format_excerpt_hint(excerpt)
    combined = " ".join(
        part.strip()
        for part in (fallback_title, fallback_summary, rule_text or "", fix_guidance or "", excerpt)
        if part and part.strip()
    ).lower()

    if language_id == "yaml" and category == "security":
        if any(token in combined for token in ("checksum", "signature", "tls verification", "shell script")):
            return FindingDraft(
                title="CI에서 외부 스크립트를 검증 없이 실행하고 있습니다",
                summary=(
                    "이 변경은 네트워크에서 가져온 내용을 검증 없이 실행 경로에 연결합니다. "
                    "CI 단계는 배포 체인의 일부라서 provenance가 약해지면 재현성과 추적성이 빠르게 무너집니다."
                    f"{excerpt_hint}"
                ),
                suggested_fix=cleaned_fix_guidance
                or (
                    "다운로드와 실행을 분리하고, checksum 또는 signature 검증을 통과한 뒤에만 "
                    "실행 경로로 넘겨 주세요."
                ),
                severity="high",
                confidence=0.88,
            )
        return FindingDraft(
            title="CI 입력을 신뢰 경계에서 한 번 더 검증해 주세요",
            summary=(
                "이 변경은 CI에서 외부 입력이나 실행 자산을 다루는 방식이 조금 느슨해 보입니다. "
                "이 구간은 재실행과 사고 분석이 모두 어려워지기 쉬운 곳입니다."
                f"{excerpt_hint}"
            ),
            suggested_fix=cleaned_fix_guidance
            or "외부 입력은 pinning, 검증, 실행을 분리해서 provenance를 남겨 주세요.",
            severity="high",
            confidence=0.8,
        )

    if language_id == "yaml" and category == "configuration":
        return FindingDraft(
            title="CI 런타임 이미지는 고정 버전으로 pinning해 주세요",
            summary=(
                "helper/service 이미지가 floating tag를 쓰면 같은 파이프라인 정의라도 실행 시점마다 "
                "동작이 달라질 수 있습니다. 디버깅과 롤백 재현성을 위해 버전 또는 digest를 고정하는 편이 안전합니다."
                f"{excerpt_hint}"
            ),
            suggested_fix=cleaned_fix_guidance
            or "helper/service 이미지는 version tag 또는 digest로 고정해 주세요.",
            severity="medium",
            confidence=0.82,
        )

    if language_id == "python" and category == "performance":
        return FindingDraft(
            title="비동기 핸들러 안에 blocking 작업이 섞이지 않게 해 주세요",
            summary=(
                "이 변경은 async request 경로 안에서 event loop를 오래 붙잡을 수 있는 작업을 수행할 가능성이 있습니다. "
                "이런 패턴은 unrelated request까지 같이 느려지게 만듭니다."
                f"{excerpt_hint}"
            ),
            suggested_fix=cleaned_fix_guidance
            or "blocking 작업은 thread pool로 보내거나 async-native client로 바꿔 주세요.",
            severity="high",
            confidence=0.85,
        )

    if language_id == "python" and category == "security":
        return FindingDraft(
            title="요청 본문을 타입 모델로 검증해 주세요",
            summary=(
                "핸들러에서 `request.json()` 같은 ad hoc 파싱으로 바로 본문을 다루면, "
                "검증 규약이 endpoint마다 흩어지고 이후 로직이 기대하는 계약도 약해집니다."
                f"{excerpt_hint}"
            ),
            suggested_fix=cleaned_fix_guidance
            or "Pydantic 모델이나 명시적인 validation step으로 HTTP 경계에서 먼저 계약을 고정해 주세요.",
            severity="medium",
            confidence=0.84,
        )

    if language_id == "sql" and category == "sql_quality":
        if "group by explicit" in combined or "grouping semantics" in combined:
            return FindingDraft(
                title="GROUP BY 순번 지정은 변경에 취약합니다",
                summary=(
                    "projection 순서에 의존하는 GROUP BY는 컬럼이 추가되거나 재배치될 때 의미가 조용히 바뀔 수 있습니다. "
                    "리뷰와 유지보수 모두 explicit column 기준이 더 안전합니다."
                    f"{excerpt_hint}"
                ),
                suggested_fix=cleaned_fix_guidance
                or "GROUP BY는 순번 대신 explicit column name 또는 alias로 바꿔 주세요.",
                severity="medium",
                confidence=0.84,
            )
        if "order by" in combined:
            return FindingDraft(
                title="재사용되는 SQL 결과는 정렬 기준을 명시해 주세요",
                summary=(
                    "LIMIT이나 sampling 성격의 쿼리는 ORDER BY가 없으면 실행 시점마다 결과가 달라질 수 있습니다. "
                    "리포트나 검증 용도로 재사용된다면 정렬 계약을 코드에 남기는 편이 안전합니다."
                    f"{excerpt_hint}"
                ),
                suggested_fix=cleaned_fix_guidance
                or "LIMIT을 쓰는 쿼리라면 의도한 정렬 기준을 ORDER BY로 함께 명시해 주세요.",
                severity="medium",
                confidence=0.8,
            )
        return FindingDraft(
            title="SQL 결과 계약을 더 명시적으로 고정해 주세요",
            summary=(
                "이 변경은 warehouse/report SQL의 해석이 projection 순서나 암묵적 DB 동작에 기대고 있을 가능성이 있습니다. "
                "리포트 성격의 쿼리는 결과 계약을 explicit하게 남기는 편이 안전합니다."
                f"{excerpt_hint}"
            ),
            suggested_fix=cleaned_fix_guidance
            or "정렬, grouping, null 처리 규칙을 쿼리 안에서 explicit하게 드러내 주세요.",
            severity="medium",
            confidence=0.76,
        )

    if language_id == "cuda":
        if "grid.sync" in combined or "cooperative launch" in combined:
            return FindingDraft(
                title="grid.sync()의 cooperative launch 계약을 드러내 주세요",
                summary=(
                    "`grid.sync()`는 cooperative launch, residency, grid 크기 계약이 이미 "
                    "호출 경계에서 보장될 때만 안전합니다. 이 변경은 그 소유권이 local patch에서 "
                    "충분히 보이지 않습니다."
                    f"{excerpt_hint}"
                ),
                suggested_fix=cleaned_fix_guidance
                or (
                    "cooperative launch 요구사항과 grid residency 가정을 launch boundary 근처에 "
                    "명시하거나, 해당 계약을 소유한 abstraction에 문서화해 주세요."
                ),
                severity="high",
                confidence=0.84,
            )
        if (
            "stream 0" in combined
            or "default-stream" in combined
            or "cudamemcpyasync" in combined
        ):
            return FindingDraft(
                title="CUDA stream 0 사용이 async 순서를 숨깁니다",
                summary=(
                    "`cudaMemcpyAsync`가 `stream 0`을 직접 사용하면 async처럼 보여도 "
                    "NULL-stream ordering에 묶일 수 있습니다. 호출자가 기대하는 overlap과 "
                    "completion 소유권이 코드에서 분명해야 합니다."
                    f"{excerpt_hint}"
                ),
                suggested_fix=cleaned_fix_guidance
                or (
                    "overlap이 필요한 작업은 명시적으로 소유한 CUDA stream에 연결하고, "
                    "stream 0 sequencing이 의도라면 그 ordering 계약을 남겨 주세요."
                ),
                severity="high",
                confidence=0.85,
            )

    if category == "security" and language_id in {"java", "javascript", "typescript", "rust", "go"}:
        return FindingDraft(
            title="신뢰 경계에서 입력 검증을 더 직접적으로 드러내 주세요",
            summary=(
                "이 변경은 외부 입력이나 실행 경계를 다루는 코드로 보여서, 검증 규약이 코드에 더 직접적으로 드러나는 편이 안전합니다."
                f"{excerpt_hint}"
            ),
            suggested_fix=cleaned_fix_guidance or "입력 검증과 실패 경로를 boundary 근처에서 명시해 주세요.",
            severity="medium",
            confidence=0.78,
        )

    return None


def _normalize_title(title: str) -> str:
    cleaned = title.strip().strip("`")
    cleaned = re.sub(r"^[A-Z][A-Z0-9.-]+(?:\s+|:)\s*", "", cleaned)
    if not cleaned:
        return "문제를 조금 더 직접적으로 드러내 주세요"
    if cleaned[0].isascii():
        return "이 변경을 조금 더 안전한 형태로 정리해 주세요"
    return cleaned


def _normalize_summary(summary: str, title: str) -> str:
    text = summary.strip()
    if not text:
        return ""
    title_prefixes = {title.strip(), title.strip("`")}
    for prefix in title_prefixes:
        if prefix and text.startswith(prefix):
            text = text[len(prefix) :].lstrip(" -:")
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return ""
    if len(text) > 220:
        text = text[:217].rstrip() + "..."
    return text


def _format_excerpt_hint(excerpt: str) -> str:
    if not excerpt:
        return ""
    lines = [line.rstrip() for line in excerpt.splitlines() if line.strip()][:2]
    if not lines:
        return ""
    compact = " / ".join(lines)
    if len(compact) > 120:
        compact = compact[:117].rstrip() + "..."
    return f" 문제로 보이는 코드는 `{compact}` 부근입니다."


def _excerpt_near_selected_line(change_snippet: str, selected_line_no: int | None) -> str:
    if selected_line_no is None:
        return ""
    for line in parse_numbered_change_snippet(change_snippet):
        if line.new_line_no == selected_line_no:
            return line.text
    return ""


def _clean_fix_guidance(fix_guidance: str | None) -> str | None:
    if not fix_guidance:
        return None
    text = re.sub(r"\s+", " ", fix_guidance).strip()
    if not text:
        return None
    if "Rule-" in text or "guidance" in text.lower():
        return None
    if not re.search(r"[가-힣]", text):
        return None
    if len(text) > 160:
        text = text[:157].rstrip() + "..."
    return text
