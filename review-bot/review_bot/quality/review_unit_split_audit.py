from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from review_bot.review_units import (
    DEFAULT_MAX_LINES_PER_REVIEW_UNIT,
    ReviewUnit,
    iter_review_units,
)


@dataclass(frozen=True)
class LogicalBlock:
    block_id: str
    start_line: int
    end_line: int


@dataclass(frozen=True)
class ReviewUnitSplitAuditCase:
    case_id: str
    language_id: str
    file_path: str
    structure_kind: str
    rationale: str
    patch: str
    logical_blocks: tuple[LogicalBlock, ...]


def load_review_unit_split_cases() -> list[ReviewUnitSplitAuditCase]:
    return [
        _python_fastapi_case(),
        _typescript_react_case(),
        _yaml_kubernetes_case(),
        _go_handler_case(),
    ]


def evaluate_review_unit_split_cases(
    cases: list[ReviewUnitSplitAuditCase],
    *,
    max_lines_per_review_unit: int = DEFAULT_MAX_LINES_PER_REVIEW_UNIT,
) -> dict[str, object]:
    results = [
        _evaluate_case(
            case,
            max_lines_per_review_unit=max_lines_per_review_unit,
        )
        for case in cases
    ]
    selected_languages = sorted(
        {
            str(result["language_id"])
            for result in results
            if result["recommendation"] == "prioritize_syntax_aware_split"
        }
    )
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "max_lines_per_review_unit": max_lines_per_review_unit,
        "summary": {
            "total_cases": len(results),
            "selected_language_count": len(selected_languages),
            "selected_languages": selected_languages,
        },
        "results": results,
    }


def render_markdown_report(report: dict[str, object]) -> str:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    selected_languages = summary.get("selected_languages")
    if isinstance(selected_languages, list) and selected_languages:
        selected_display = ", ".join(f"`{item}`" for item in selected_languages)
    else:
        selected_display = "(none)"
    lines = [
        "# Review Unit Split Audit",
        "",
        f"- generated_at: `{report.get('generated_at')}`",
        f"- max_lines_per_review_unit: `{report.get('max_lines_per_review_unit')}`",
        f"- total_cases: `{summary.get('total_cases', 0)}`",
        f"- selected_language_count: `{summary.get('selected_language_count', 0)}`",
        f"- selected_languages: {selected_display}",
        "",
        "## Selection Rule",
        "",
        (
            "현재 fixed-line hunk split이 하나의 logical block을 여러 review unit으로 자르고,"
            " 그 언어가 indentation/tree 구조 중심이면 `prioritize_syntax_aware_split`로 분류한다."
        ),
        "",
        "## Case Summary",
        "",
        (
            "| case_id | language | structure | review_units | split_blocks |"
            " mid_block_starts | recommendation |"
        ),
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    results = report.get("results") if isinstance(report.get("results"), list) else []
    for result in results:
        metrics = result.get("metrics") if isinstance(result.get("metrics"), dict) else {}
        lines.append(
            "| "
            + " | ".join(
                [
                    str(result.get("case_id") or ""),
                    str(result.get("language_id") or ""),
                    str(result.get("structure_kind") or ""),
                    str(metrics.get("review_unit_count", 0)),
                    str(metrics.get("split_logical_block_count", 0)),
                    str(metrics.get("mid_block_unit_start_count", 0)),
                    str(result.get("recommendation") or ""),
                ]
            )
            + " |"
        )

    lines.extend(["", "## Priority Languages", ""])
    if isinstance(selected_languages, list) and selected_languages:
        for language_id in selected_languages:
            reasons = [
                str(result.get("rationale") or "")
                for result in results
                if result.get("language_id") == language_id
                and result.get("recommendation") == "prioritize_syntax_aware_split"
            ]
            reason = reasons[0] if reasons else "needs syntax-aware split"
            lines.append(f"- `{language_id}`: {reason}")
    else:
        lines.append("- No language currently exceeds the syntax-aware split priority threshold.")

    monitor_cases = [
        result
        for result in results
        if result.get("recommendation") == "monitor_current_hunk_split"
    ]
    if monitor_cases:
        lines.extend(["", "## Monitor Only", ""])
        for result in monitor_cases:
            lines.append(
                f"- `{result.get('language_id')}`: {result.get('rationale')}"
            )

    lines.extend(["", "## Detailed Findings", ""])
    for result in results:
        metrics = result.get("metrics") if isinstance(result.get("metrics"), dict) else {}
        lines.extend(
            [
                f"### {result.get('case_id')}",
                "",
                f"- file_path: `{result.get('file_path')}`",
                f"- recommendation: `{result.get('recommendation')}`",
                f"- review_unit_count: `{metrics.get('review_unit_count', 0)}`",
                (
                    "- logical_block_ids_split: "
                    f"{', '.join(metrics.get('split_logical_block_ids', [])) or '(none)'}"
                ),
                f"- mid_block_unit_starts: `{metrics.get('mid_block_unit_start_count', 0)}`",
                f"- rationale: {result.get('rationale')}",
                "",
            ]
        )
    return "\n".join(lines)


def _evaluate_case(
    case: ReviewUnitSplitAuditCase,
    *,
    max_lines_per_review_unit: int,
) -> dict[str, object]:
    review_units = iter_review_units(
        case.patch,
        max_lines_per_review_unit=max_lines_per_review_unit,
    )
    unit_ranges = [_unit_range(review_unit) for review_unit in review_units]
    split_block_ids = [
        block.block_id
        for block in case.logical_blocks
        if len(
            [
                unit_range
                for unit_range in unit_ranges
                if _ranges_overlap(unit_range, (block.start_line, block.end_line))
            ]
        )
        > 1
    ]
    mid_block_unit_starts = sum(
        1
        for start_line, _end_line in unit_ranges
        if any(block.start_line < start_line <= block.end_line for block in case.logical_blocks)
    )
    recommendation = _recommendation_for_case(
        structure_kind=case.structure_kind,
        split_block_ids=split_block_ids,
    )
    return {
        "case_id": case.case_id,
        "language_id": case.language_id,
        "file_path": case.file_path,
        "structure_kind": case.structure_kind,
        "recommendation": recommendation,
        "rationale": case.rationale,
        "metrics": {
            "review_unit_count": len(review_units),
            "split_logical_block_count": len(split_block_ids),
            "split_logical_block_ids": split_block_ids,
            "mid_block_unit_start_count": mid_block_unit_starts,
        },
    }


def _recommendation_for_case(*, structure_kind: str, split_block_ids: list[str]) -> str:
    if not split_block_ids:
        return "current_hunk_split_ok"
    if structure_kind in {"indentation", "jsx_tree", "yaml_tree"}:
        return "prioritize_syntax_aware_split"
    return "monitor_current_hunk_split"


def _unit_range(review_unit: ReviewUnit) -> tuple[int, int]:
    if review_unit.candidate_line_nos:
        return review_unit.candidate_line_nos[0], review_unit.candidate_line_nos[-1]
    if review_unit.default_line_no is not None:
        return review_unit.default_line_no, review_unit.default_line_no
    return 0, 0


def _ranges_overlap(left: tuple[int, int], right: tuple[int, int]) -> bool:
    return left[0] <= right[1] and right[0] <= left[1]


def _python_fastapi_case() -> ReviewUnitSplitAuditCase:
    lines = [
        "from fastapi import APIRouter, HTTPException",
        "",
        "router = APIRouter()",
        "",
        "@router.post('/audit')",
        "async def create_audit(payload: dict[str, object]) -> dict[str, object]:",
        "    normalized: dict[str, object] = {}",
    ]
    for index in range(1, 21):
        lines.extend(
            [
                f"    value_{index:02d} = payload.get('field_{index:02d}')",
                f"    if value_{index:02d} is None:",
                f"        raise HTTPException(status_code=400, detail='missing field_{index:02d}')",
                f"    normalized['field_{index:02d}'] = value_{index:02d}",
            ]
        )
    lines.append("    return normalized")
    return ReviewUnitSplitAuditCase(
        case_id="python_fastapi_long_handler",
        language_id="python",
        file_path="app/api/audit.py",
        structure_kind="indentation",
        rationale=(
            "Python handler body가 indentation으로만 경계를 표현하므로 fixed-line split이"
            " mid-block unit을 만들면 anchor와 summary 문맥이 급격히 약해진다."
        ),
        patch=_build_added_patch(lines),
        logical_blocks=(
            LogicalBlock(
                block_id="create_audit_handler",
                start_line=5,
                end_line=len(lines),
            ),
        ),
    )


def _typescript_react_case() -> ReviewUnitSplitAuditCase:
    lines = [
        "type Props = { items: string[] };",
        "",
        "export function ReviewAuditPanel({ items }: Props) {",
        "  return (",
        "    <section className=\"review-audit-panel\">",
        "      <header>",
        "        <h2>Audit</h2>",
        "      </header>",
        "      <ul>",
    ]
    for index in range(1, 20):
        item_index = (index - 1) % 3
        lines.extend(
            [
                "        <li className=\"audit-row\">",
                f"          <span className=\"audit-label\">Section {index:02d}</span>",
                f"          <span className=\"audit-value\">{{items[{item_index}]}}</span>",
                "        </li>",
            ]
        )
    lines.extend(
        [
            "      </ul>",
            "    </section>",
            "  );",
            "}",
        ]
    )
    return ReviewUnitSplitAuditCase(
        case_id="typescript_react_long_component",
        language_id="typescript",
        file_path="ui/ReviewAuditPanel.tsx",
        structure_kind="jsx_tree",
        rationale=(
            "TSX component는 JSX tree 단위가 review 문맥인데 fixed-line split이 tree 중간에서"
            " 끊기면 component intent와 위험 위치를 함께 보기 어렵다."
        ),
        patch=_build_added_patch(lines),
        logical_blocks=(
            LogicalBlock(
                block_id="review_audit_panel_component",
                start_line=3,
                end_line=len(lines),
            ),
        ),
    )


def _yaml_kubernetes_case() -> ReviewUnitSplitAuditCase:
    lines = [
        "apiVersion: apps/v1",
        "kind: Deployment",
        "metadata:",
        "  name: review-audit",
        "spec:",
        "  template:",
        "    spec:",
        "      containers:",
        "        - name: api",
        "          image: registry.local/review-audit:latest",
        "          env:",
    ]
    for index in range(1, 36):
        lines.extend(
            [
                f"            - name: FEATURE_FLAG_{index:02d}",
                "              value: \"enabled\"",
            ]
        )
    lines.extend(
        [
            "          resources:",
            "            limits:",
            "              cpu: \"1\"",
        ]
    )
    return ReviewUnitSplitAuditCase(
        case_id="yaml_k8s_long_container_env",
        language_id="yaml",
        file_path="deploy/review-audit.yaml",
        structure_kind="yaml_tree",
        rationale=(
            "YAML manifest는 indentation tree가 곧 semantic scope라서"
            " container/env block 중간 split은"
            " wrong anchor와 rule explanation drift를 만들기 쉽다."
        ),
        patch=_build_added_patch(lines),
        logical_blocks=(
            LogicalBlock(
                block_id="deployment_container_block",
                start_line=9,
                end_line=len(lines),
            ),
        ),
    )


def _go_handler_case() -> ReviewUnitSplitAuditCase:
    lines = [
        "package audit",
        "",
        "import (",
        "    \"encoding/json\"",
        "    \"net/http\"",
        ")",
        "",
        "type request struct {",
        "    Email string `json:\"email\"`",
        "}",
        "",
        "func (h Handler) ServeHTTP(w http.ResponseWriter, r *http.Request) {",
        "    var req request",
        "    decoder := json.NewDecoder(r.Body)",
        "    if err := decoder.Decode(&req); err != nil {",
        "        http.Error(w, \"bad request\", http.StatusBadRequest)",
        "        return",
        "    }",
    ]
    for index in range(1, 18):
        lines.extend(
            [
                f"    if req.Email == \"case-{index:02d}\" {{",
                f"        http.Error(w, \"blocked case {index:02d}\", http.StatusBadRequest)",
                "        return",
                "    }",
            ]
        )
    lines.extend(
        [
            "    w.WriteHeader(http.StatusCreated)",
            "}",
        ]
    )
    return ReviewUnitSplitAuditCase(
        case_id="go_http_long_handler",
        language_id="go",
        file_path="handlers/audit.go",
        structure_kind="brace_block",
        rationale=(
            "Go long handler도 logical block이 둘로 갈리지만 brace delimiter가 남아 있어 우선순위는"
            " syntax-aware 도입보다 monitor 쪽에 둔다."
        ),
        patch=_build_added_patch(lines),
        logical_blocks=(
            LogicalBlock(
                block_id="serve_http_handler",
                start_line=12,
                end_line=len(lines),
            ),
        ),
    )


def _build_added_patch(lines: list[str]) -> str:
    header = f"@@ -0,0 +1,{len(lines)} @@"
    return "\n".join([header, *[f"+{line}" if line else "+" for line in lines]])
