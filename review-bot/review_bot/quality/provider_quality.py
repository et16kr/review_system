from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
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
    provider_runtime: dict[str, object] | None = None,
) -> dict[str, object]:
    results = [_evaluate_case(provider=provider, case=case) for case in cases]
    failed_cases = [result for result in results if result["status"] != "passed"]
    report = {
        "provider": provider_name,
        "status": "passed" if not failed_cases else "failed",
        "summary": {
            "total_cases": len(results),
            "passed_cases": len(results) - len(failed_cases),
            "failed_cases": len(failed_cases),
        },
        "results": results,
    }
    if provider_runtime:
        report["provider_runtime"] = provider_runtime
    return report


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
    runtime = _provider_runtime_dict(report.get("provider_runtime"))
    if runtime:
        lines.append(f"- provider_runtime: `{_render_provider_runtime(runtime)}`")
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


def build_provider_quality_comparison(
    *,
    stub_report: dict[str, object],
    openai_report: dict[str, object],
    generated_at: str | None = None,
    corpus_revision: str = "unknown",
) -> dict[str, object]:
    stub_results = _results_by_case_id(stub_report)
    openai_results = _results_by_case_id(openai_report)
    stub_status = _report_status(stub_report)
    openai_status = _report_status(openai_report)
    if generated_at is None:
        generated_at = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")

    if openai_status == "skipped":
        return {
            "generated_at": generated_at,
            "corpus_revision": corpus_revision,
            "stub_status": stub_status,
            "openai_status": openai_status,
            "stub_provider_runtime": _provider_runtime_dict(stub_report.get("provider_runtime")),
            "openai_provider_runtime": _provider_runtime_dict(openai_report.get("provider_runtime")),
            "openai_skip_reason": str(openai_report.get("skip_reason") or ""),
            "case_count": len(stub_results),
            "compared_case_count": 0,
            "case_deltas": [],
            "human_review_required": False,
            "recommended_next_action": "defer_openai_comparison_until_api_key_available",
        }

    case_ids = sorted(set(stub_results) | set(openai_results))
    case_deltas = [
        _case_comparison_delta(case_id, stub_results.get(case_id), openai_results.get(case_id))
        for case_id in case_ids
    ]
    human_review_required = (
        openai_status != "passed"
        or any(bool(delta["human_review_required"]) for delta in case_deltas)
    )
    return {
        "generated_at": generated_at,
        "corpus_revision": corpus_revision,
        "stub_status": stub_status,
        "openai_status": openai_status,
        "stub_provider_runtime": _provider_runtime_dict(stub_report.get("provider_runtime")),
        "openai_provider_runtime": _provider_runtime_dict(openai_report.get("provider_runtime")),
        "openai_skip_reason": "",
        "case_count": len(stub_results),
        "compared_case_count": len(case_deltas),
        "case_deltas": case_deltas,
        "human_review_required": human_review_required,
        "recommended_next_action": (
            "review_provider_deltas_before_tuning"
            if human_review_required
            else "accept_current_provider_outputs"
        ),
    }


def render_provider_comparison_markdown(report: dict[str, object]) -> str:
    lines = [
        "# Review Bot Provider Comparison",
        "",
        f"- generated_at: `{report.get('generated_at')}`",
        f"- corpus_revision: `{report.get('corpus_revision')}`",
        f"- stub_status: `{report.get('stub_status')}`",
        f"- openai_status: `{report.get('openai_status')}`",
    ]
    stub_runtime = _provider_runtime_dict(report.get("stub_provider_runtime"))
    if stub_runtime:
        lines.append(f"- stub_provider_runtime: `{_render_provider_runtime(stub_runtime)}`")
    openai_runtime = _provider_runtime_dict(report.get("openai_provider_runtime"))
    if openai_runtime:
        lines.append(f"- openai_provider_runtime: `{_render_provider_runtime(openai_runtime)}`")
    if report.get("openai_skip_reason"):
        lines.append(f"- openai_skip_reason: `{report['openai_skip_reason']}`")
    lines.extend(
        [
            f"- case_count: `{report.get('case_count', 0)}`",
            f"- compared_case_count: `{report.get('compared_case_count', 0)}`",
            f"- human_review_required: `{report.get('human_review_required')}`",
            f"- recommended_next_action: `{report.get('recommended_next_action')}`",
            "",
        ]
    )

    if report.get("openai_status") == "skipped":
        lines.extend(
            [
                "OpenAI comparison was skipped because no OpenAI artifact was available.",
                "Capture again with `OPENAI_API_KEY` before changing prompt or ranking weights.",
                "",
            ]
        )

    lines.extend(
        [
            "## Review Rubric",
            "",
            "| Axis | Check |",
            "| --- | --- |",
            "| groundedness | Does the draft avoid facts missing from the snippet? |",
            "| evidence_anchoring | Does title/summary connect to line evidence? |",
            "| claim_strength | Does it avoid overclaiming uncertain risk? |",
            "| specificity | Does it preserve language/profile/context details? |",
            "| actionability | Is the suggested fix concrete enough to act on? |",
            "| brevity | Is it concise enough for review UI? |",
            "| noise_risk | Does it avoid duplicate/noisy phrasing? |",
            "",
        ]
    )

    case_deltas = report.get("case_deltas")
    if not isinstance(case_deltas, list) or not case_deltas:
        lines.extend(["## Case Deltas", "", "(no comparable OpenAI cases)", ""])
        return "\n".join(lines)

    lines.extend(
        [
            "## Case Deltas",
            "",
            "| case_id | recommendation | status | title_delta | summary_delta | "
            "fix_delta | required_delta | line_mismatch | publish_mismatch |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for delta in case_deltas:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(delta.get("case_id") or ""),
                    str(delta.get("review_recommendation") or ""),
                    f"{delta.get('stub_status')} -> {delta.get('openai_status')}",
                    str(delta.get("title_length_delta")),
                    str(delta.get("summary_length_delta")),
                    str(delta.get("suggested_fix_length_delta")),
                    str(delta.get("required_missing_delta")),
                    str(delta.get("line_anchor_mismatch")),
                    str(delta.get("should_publish_mismatch")),
                ]
            )
            + " |"
        )

    review_items = [
        delta for delta in case_deltas if bool(delta.get("human_review_required"))
    ]
    if review_items:
        lines.extend(["", "## Human Review Checklist", ""])
        for delta in review_items:
            signals = delta.get("review_signals")
            signal_text = (
                ", ".join(str(item) for item in signals)
                if isinstance(signals, list)
                else ""
            )
            lines.extend(
                [
                    f"### {delta.get('case_id')}",
                    "",
                    f"- recommendation: `{delta.get('review_recommendation')}`",
                    f"- signals: {signal_text or '-'}",
                    f"- stub_title: {delta.get('stub_title') or '-'}",
                    f"- openai_title: {delta.get('openai_title') or '-'}",
                    "",
                ]
            )

    lines.extend(
        [
            "## Tuning Guardrail",
            "",
            "Do not change prompt or ranking weights from this artifact alone.",
            "Use this summary to create a targeted regression or a separate tuning task first.",
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


def _provider_runtime_dict(payload: object) -> dict[str, object] | None:
    if not isinstance(payload, dict) or not payload:
        return None
    return {str(key): value for key, value in payload.items()}


def _render_provider_runtime(runtime: dict[str, object]) -> str:
    parts: list[str] = []
    for key in (
        "configured_provider",
        "effective_provider",
        "fallback_used",
        "configured_model",
        "endpoint_base_url",
        "transport_class",
    ):
        value = runtime.get(key)
        if value is None or value == "":
            continue
        parts.append(f"{key}={value}")
    return ", ".join(parts) or "unknown"


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


def _report_status(report: dict[str, object]) -> str:
    return str(report.get("status") or "unknown")


def _results_by_case_id(report: dict[str, object]) -> dict[str, dict[str, object]]:
    raw_results = report.get("results")
    if not isinstance(raw_results, list):
        return {}
    results: dict[str, dict[str, object]] = {}
    for raw_result in raw_results:
        if not isinstance(raw_result, dict):
            continue
        case_id = str(raw_result.get("case_id") or "").strip()
        if case_id:
            results[case_id] = raw_result
    return results


def _case_comparison_delta(
    case_id: str,
    stub_result: dict[str, object] | None,
    openai_result: dict[str, object] | None,
) -> dict[str, object]:
    if stub_result is None or openai_result is None:
        return {
            "case_id": case_id,
            "stub_status": _result_status(stub_result),
            "openai_status": _result_status(openai_result),
            "title_length_delta": None,
            "summary_length_delta": None,
            "suggested_fix_length_delta": None,
            "required_missing_delta": None,
            "forbidden_terms_delta": None,
            "line_anchor_mismatch": False,
            "should_publish_mismatch": False,
            "stub_title": _draft_field(stub_result, "title"),
            "openai_title": _draft_field(openai_result, "title"),
            "human_review_required": True,
            "review_recommendation": "defer",
            "review_signals": ["missing comparable provider result"],
        }

    signals: list[str] = []
    title_delta = _metric_int(openai_result, "title_length") - _metric_int(
        stub_result,
        "title_length",
    )
    summary_delta = _metric_int(openai_result, "summary_length") - _metric_int(
        stub_result,
        "summary_length",
    )
    fix_delta = _metric_int(openai_result, "suggested_fix_length") - _metric_int(
        stub_result,
        "suggested_fix_length",
    )
    required_delta = len(_list_field(openai_result, "missing_terms")) - len(
        _list_field(stub_result, "missing_terms")
    )
    forbidden_delta = len(_list_field(openai_result, "forbidden_terms_present")) - len(
        _list_field(stub_result, "forbidden_terms_present")
    )
    line_anchor_mismatch = _line_ok(stub_result) != _line_ok(openai_result)
    should_publish_mismatch = _should_publish(stub_result) != _should_publish(openai_result)

    if _result_status(stub_result) != _result_status(openai_result):
        signals.append("status mismatch")
    if should_publish_mismatch:
        signals.append("should_publish mismatch")
    if line_anchor_mismatch:
        signals.append("line anchoring mismatch")
    if required_delta > 0:
        signals.append("required term coverage regression")
    if forbidden_delta > 0:
        signals.append("forbidden term regression")
    if abs(title_delta) > 15:
        signals.append("large title length delta")
    if abs(summary_delta) > 120:
        signals.append("large summary length delta")
    if abs(fix_delta) > 120:
        signals.append("large suggested_fix length delta")

    human_review_required = bool(signals)
    return {
        "case_id": case_id,
        "stub_status": _result_status(stub_result),
        "openai_status": _result_status(openai_result),
        "title_length_delta": title_delta,
        "summary_length_delta": summary_delta,
        "suggested_fix_length_delta": fix_delta,
        "required_missing_delta": required_delta,
        "forbidden_terms_delta": forbidden_delta,
        "line_anchor_mismatch": line_anchor_mismatch,
        "should_publish_mismatch": should_publish_mismatch,
        "stub_title": _draft_field(stub_result, "title"),
        "openai_title": _draft_field(openai_result, "title"),
        "human_review_required": human_review_required,
        "review_recommendation": "human_review" if human_review_required else "accept",
        "review_signals": signals,
    }


def _result_status(result: dict[str, object] | None) -> str:
    if result is None:
        return "missing"
    return str(result.get("status") or "unknown")


def _metric_int(result: dict[str, object], key: str) -> int:
    metrics = result.get("metrics") if isinstance(result.get("metrics"), dict) else {}
    value = metrics.get(key, 0)
    return int(value) if value is not None else 0


def _list_field(result: dict[str, object], key: str) -> list[object]:
    value = result.get(key)
    return value if isinstance(value, list) else []


def _line_ok(result: dict[str, object]) -> bool:
    metrics = result.get("metrics") if isinstance(result.get("metrics"), dict) else {}
    return bool(metrics.get("line_no_in_candidates"))


def _should_publish(result: dict[str, object]) -> object:
    draft = result.get("draft") if isinstance(result.get("draft"), dict) else {}
    return draft.get("should_publish")


def _draft_field(result: dict[str, object] | None, key: str) -> str:
    if result is None:
        return ""
    draft = result.get("draft") if isinstance(result.get("draft"), dict) else {}
    return str(draft.get(key) or "")
