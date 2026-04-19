from __future__ import annotations

import re

from app.providers.base import FindingDraft, ReviewCommentProvider
from app.providers.change_analysis import (
    classify_issue,
    extract_changed_excerpt,
    parse_numbered_change_snippet,
    requires_direct_signal,
    select_candidate_line,
)


class StubReviewCommentProvider(ReviewCommentProvider):
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
        del rule_no, rule_text

        excerpt = extract_changed_excerpt(change_snippet or "")
        issue = classify_issue(excerpt, category, title, summary)
        selected_line_no = select_candidate_line(
            change_snippet=change_snippet or "",
            candidate_line_nos=candidate_line_nos,
            issue=issue,
        )
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
                "이 변경에서는 `malloc/free`로 버퍼 수명을 직접 관리하고 있습니다. "
                "이 방식은 분기 추가나 중간 반환이 생길 때 "
                "해제 누락과 소유권 혼동으로 이어지기 쉽습니다."
                f"{excerpt_hint}"
            ),
            suggested_fix=(
                "버퍼 수명은 객체에 맡기고, 소유권이 필요한 경우에도 "
                "직접 `free()`를 호출하는 형태는 피하세요.\n\n"
                "예시:\n"
                "```cpp\n"
                "std::vector<char> buffer(required_size);\n"
                "fill_buffer(buffer.data(), buffer.size());\n"
                "use_buffer(buffer.data(), buffer.size());\n"
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
    )


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
