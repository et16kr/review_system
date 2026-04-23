from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

from review_bot.providers.base import FindingDraft, ReviewCommentProvider


@dataclass(frozen=True)
class ProviderQualityCase:
    case_id: str
    file_path: str
    language_id: str | None
    profile_id: str | None
    context_id: str | None
    dialect_id: str | None
    category: str | None
    rule_no: str
    rule_title: str
    rule_summary: str
    rule_text: str | None
    fix_guidance: str | None
    change_snippet: str
    candidate_line_nos: tuple[int, ...]
    expected: dict[str, Any]


def load_provider_quality_cases(path: Path | None = None) -> list[ProviderQualityCase]:
    if path is None:
        case_text = (
            resources.files("review_bot.quality")
            .joinpath("provider_quality_cases.json")
            .read_text(encoding="utf-8")
        )
    else:
        case_text = path.read_text(encoding="utf-8")
    payload = json.loads(case_text)
    if not isinstance(payload, list):
        raise ValueError("provider quality cases must be a JSON list")
    return [_case_from_payload(item) for item in payload]


def evaluate_provider_quality(
    *,
    provider: ReviewCommentProvider,
    cases: list[ProviderQualityCase],
    provider_name: str,
) -> dict[str, object]:
    results = [_evaluate_case(provider=provider, case=case) for case in cases]
    failed_cases = [result for result in results if result["status"] != "passed"]
    return {
        "provider": provider_name,
        "status": "passed" if not failed_cases else "failed",
        "summary": {
            "total_cases": len(results),
            "passed_cases": len(results) - len(failed_cases),
            "failed_cases": len(failed_cases),
        },
        "results": results,
    }


def render_markdown_report(report: dict[str, object]) -> str:
    provider = str(report.get("provider") or "unknown")
    status = str(report.get("status") or "unknown")
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    results = report.get("results") if isinstance(report.get("results"), list) else []
    lines = [
        "# Review Bot Provider Quality",
        "",
        f"- provider: `{provider}`",
        f"- status: `{status}`",
    ]
    if report.get("skip_reason"):
        lines.append(f"- skip_reason: `{report['skip_reason']}`")
    lines.extend(
        [
            f"- total_cases: `{summary.get('total_cases', 0)}`",
            f"- passed_cases: `{summary.get('passed_cases', 0)}`",
            f"- failed_cases: `{summary.get('failed_cases', 0)}`",
            "",
            "## Case Summary",
            "",
        ]
    )
    if not results:
        lines.extend(["(no cases)", ""])
        return "\n".join(lines)

    lines.extend(
        [
            "| case_id | status | title_length | line_ok | missing_terms | forbidden_terms |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for result in results:
        metrics = result.get("metrics") if isinstance(result.get("metrics"), dict) else {}
        lines.append(
            "| "
            + " | ".join(
                [
                    str(result.get("case_id") or ""),
                    str(result.get("status") or ""),
                    str(metrics.get("title_length", 0)),
                    str(metrics.get("line_no_in_candidates", False)),
                    ", ".join(str(item) for item in result.get("missing_terms", [])) or "-",
                    ", ".join(str(item) for item in result.get("forbidden_terms_present", []))
                    or "-",
                ]
            )
            + " |"
        )

    failed_results = [result for result in results if result.get("status") != "passed"]
    if failed_results:
        lines.extend(["", "## Failures", ""])
        for result in failed_results:
            lines.extend(
                [
                    f"### {result.get('case_id')}",
                    "",
                    *[f"- {failure}" for failure in result.get("failures", [])],
                    "",
                ]
            )
    return "\n".join(lines)


def _case_from_payload(payload: object) -> ProviderQualityCase:
    if not isinstance(payload, dict):
        raise ValueError("provider quality case must be an object")
    return ProviderQualityCase(
        case_id=str(payload["case_id"]),
        file_path=str(payload["file_path"]),
        language_id=_optional_str(payload.get("language_id")),
        profile_id=_optional_str(payload.get("profile_id")),
        context_id=_optional_str(payload.get("context_id")),
        dialect_id=_optional_str(payload.get("dialect_id")),
        category=_optional_str(payload.get("category")),
        rule_no=str(payload["rule_no"]),
        rule_title=str(payload["rule_title"]),
        rule_summary=str(payload["rule_summary"]),
        rule_text=_optional_str(payload.get("rule_text")),
        fix_guidance=_optional_str(payload.get("fix_guidance")),
        change_snippet=str(payload["change_snippet"]),
        candidate_line_nos=tuple(int(item) for item in payload.get("candidate_line_nos", [])),
        expected=dict(payload.get("expected") or {}),
    )


def _evaluate_case(
    *,
    provider: ReviewCommentProvider,
    case: ProviderQualityCase,
) -> dict[str, object]:
    draft = provider.build_draft(
        file_path=case.file_path,
        rule_no=case.rule_no,
        title=case.rule_title,
        summary=case.rule_summary,
        rule_text=case.rule_text,
        fix_guidance=case.fix_guidance,
        category=case.category,
        change_snippet=case.change_snippet,
        line_no=case.candidate_line_nos[0] if case.candidate_line_nos else None,
        candidate_line_nos=case.candidate_line_nos,
        language_id=case.language_id,
        profile_id=case.profile_id,
        context_id=case.context_id,
        dialect_id=case.dialect_id,
    )
    metrics = _draft_metrics(draft=draft, case=case)
    failures = _validate_draft(draft=draft, case=case, metrics=metrics)
    return {
        "case_id": case.case_id,
        "status": "passed" if not failures else "failed",
        "failures": failures,
        "missing_terms": metrics["missing_terms"],
        "forbidden_terms_present": metrics["forbidden_terms_present"],
        "metrics": metrics,
        "draft": {
            "title": draft.title,
            "summary": draft.summary,
            "suggested_fix": draft.suggested_fix,
            "should_publish": draft.should_publish,
            "severity": draft.severity,
            "confidence": draft.confidence,
            "line_no": draft.line_no,
            "evidence_snippet": draft.evidence_snippet,
        },
    }


def _draft_metrics(*, draft: FindingDraft, case: ProviderQualityCase) -> dict[str, object]:
    expected = case.expected
    combined_text = "\n".join(
        str(part or "")
        for part in (
            draft.title,
            draft.summary,
            draft.suggested_fix,
            draft.evidence_snippet,
        )
    )
    missing_terms = [
        term
        for term in expected.get("required_terms", [])
        if str(term).lower() not in combined_text.lower()
    ]
    forbidden_terms_present = [
        term
        for term in expected.get("forbidden_terms", [])
        if str(term).lower() in combined_text.lower()
    ]
    return {
        "title_length": len(draft.title or ""),
        "summary_length": len(draft.summary or ""),
        "suggested_fix_length": len(draft.suggested_fix or ""),
        "evidence_snippet_present": bool(draft.evidence_snippet),
        "line_no_in_candidates": draft.line_no in case.candidate_line_nos,
        "should_publish": draft.should_publish,
        "missing_terms": missing_terms,
        "forbidden_terms_present": forbidden_terms_present,
    }


def _validate_draft(
    *,
    draft: FindingDraft,
    case: ProviderQualityCase,
    metrics: dict[str, object],
) -> list[str]:
    expected = case.expected
    failures: list[str] = []
    if draft.should_publish != bool(expected.get("should_publish", True)):
        expected_publish = expected.get("should_publish")
        failures.append(
            f"should_publish expected {expected_publish} "
            f"but got {draft.should_publish}"
        )
    _check_max_length(failures, "title", metrics["title_length"], expected.get("title_max_chars"))
    _check_max_length(
        failures,
        "summary",
        metrics["summary_length"],
        expected.get("summary_max_chars"),
    )
    _check_max_length(
        failures,
        "suggested_fix",
        metrics["suggested_fix_length"],
        expected.get("suggested_fix_max_chars"),
    )
    if expected.get("line_no_in_candidates", True) and not metrics["line_no_in_candidates"]:
        failures.append(f"line_no {draft.line_no} is not in {case.candidate_line_nos}")
    if expected.get("evidence_required") and not metrics["evidence_snippet_present"]:
        failures.append("evidence_snippet is required")
    if metrics["missing_terms"]:
        failures.append(f"missing required terms: {', '.join(metrics['missing_terms'])}")
    if metrics["forbidden_terms_present"]:
        failures.append(
            f"forbidden terms present: {', '.join(metrics['forbidden_terms_present'])}"
        )
    return failures


def _check_max_length(
    failures: list[str],
    field_name: str,
    actual: object,
    maximum: object,
) -> None:
    if maximum is None:
        return
    if int(actual) > int(maximum):
        failures.append(f"{field_name} length {actual} exceeds {maximum}")


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None
