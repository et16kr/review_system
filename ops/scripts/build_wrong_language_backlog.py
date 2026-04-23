#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib import parse, request

ROOT = Path("/home/et16/work/review_system")
DEFAULT_OUTPUT_DIR = ROOT / "docs" / "baselines" / "review_bot"
PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}
ACTIONABILITY_ORDER = {
    "fix_detector": 0,
    "inspect_thread": 1,
    "update_policy_or_fixture": 2,
    "ignore_for_detector_backlog": 3,
}


def fetch_json(url: str) -> dict | list:
    with request.urlopen(url, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def build_url(base_url: str, path: str, **params: str) -> str:
    filtered = {key: value for key, value in params.items() if value}
    query = parse.urlencode(filtered)
    return f"{base_url.rstrip('/')}{path}" + (f"?{query}" if query else "")


def _format_candidate_title(item: dict[str, object]) -> str:
    detected = str(item.get("detected_language_id") or "unknown")
    expected = str(item.get("expected_language_id") or "unknown")
    count = int(item.get("count") or 0)
    return f"`{detected}` -> `{expected}` x{count}"


def _candidate_sort_key(item: dict[str, object]) -> tuple[object, ...]:
    return (
        PRIORITY_ORDER.get(str(item.get("priority") or "low"), 99),
        ACTIONABILITY_ORDER.get(str(item.get("actionability") or "inspect_thread"), 99),
        -int(item.get("count") or 0),
        str(item.get("detected_language_id") or ""),
        str(item.get("expected_language_id") or ""),
        str(item.get("path_pattern") or ""),
    )


def _is_smoke_candidate(item: dict[str, object]) -> bool:
    return (
        str(item.get("provenance") or "unknown") == "smoke"
        or str(item.get("triage_cause") or "needs_inspection") == "synthetic_smoke"
        or str(item.get("actionability") or "inspect_thread")
        == "ignore_for_detector_backlog"
    )


def _append_candidate_section(
    lines: list[str],
    *,
    title: str,
    candidates: list[dict[str, object]],
    empty_message: str,
) -> None:
    lines.extend([f"## {title}", ""])
    if not candidates:
        lines.extend([empty_message, ""])
        return
    for index, item in enumerate(candidates, start=1):
        profile_id = str(item.get("profile_id") or "default")
        context_id = str(item.get("context_id") or "generic")
        path_pattern = str(item.get("path_pattern") or "<unknown>")
        priority = str(item.get("priority") or "low")
        provenance = str(item.get("provenance") or "unknown")
        triage_cause = str(item.get("triage_cause") or "needs_inspection")
        actionability = str(item.get("actionability") or "inspect_thread")
        suggested_action = str(item.get("suggested_action") or "")
        lines.extend(
            [
                f"### {index}. {_format_candidate_title(item)}",
                "",
                f"- priority: `{priority}`",
                f"- provenance: `{provenance}`",
                f"- triage_cause: `{triage_cause}`",
                f"- actionability: `{actionability}`",
                f"- profile/context: `{profile_id}` / `{context_id}`",
                f"- path_pattern: `{path_pattern}`",
                f"- suggested_action: {suggested_action}",
                "",
            ]
        )


def render_markdown(
    *,
    bot_base_url: str,
    project_ref: str | None,
    window: str,
    report: dict | list,
    min_count: int,
    max_items: int,
    include_smoke: bool = False,
    only_actionable: bool = False,
    show_needs_inspection: bool = False,
) -> str:
    generated_at = datetime.now(UTC).isoformat()
    payload = report if isinstance(report, dict) else {}
    all_candidates = [
        item
        for item in payload.get("triage_candidates", [])
        if int(item.get("count") or 0) >= min_count
    ]
    candidates = sorted(all_candidates, key=_candidate_sort_key)[:max_items]
    non_smoke_candidates = [
        item for item in candidates if include_smoke or not _is_smoke_candidate(item)
    ]
    detector_fix_candidates = [
        item
        for item in non_smoke_candidates
        if str(item.get("actionability") or "inspect_thread") == "fix_detector"
    ]
    wrong_thread_candidates = [
        item
        for item in non_smoke_candidates
        if str(item.get("triage_cause") or "needs_inspection") == "wrong_thread_target"
    ]
    policy_candidates = [
        item
        for item in non_smoke_candidates
        if str(item.get("actionability") or "inspect_thread") == "update_policy_or_fixture"
    ]
    needs_inspection_candidates = [
        item
        for item in non_smoke_candidates
        if str(item.get("triage_cause") or "needs_inspection") == "needs_inspection"
    ]
    smoke_candidates = [item for item in candidates if _is_smoke_candidate(item)]

    lines = [
        "# Review Bot Wrong-Language Backlog",
        "",
        f"- generated_at_utc: `{generated_at}`",
        f"- bot_base_url: `{bot_base_url}`",
        f"- project_ref: `{project_ref or 'all'}`",
        f"- window: `{window}`",
        f"- min_count: `{min_count}`",
        f"- max_items: `{max_items}`",
        f"- include_smoke: `{include_smoke}`",
        f"- only_actionable: `{only_actionable}`",
        f"- show_needs_inspection: `{show_needs_inspection}`",
        "",
        "## Summary",
        "",
        f"- total_events: `{payload.get('total_events', 0)}`",
        f"- smoke_events: `{payload.get('smoke_events', 0)}`",
        f"- production_events: `{payload.get('production_events', 0)}`",
        f"- unknown_provenance_events: `{payload.get('unknown_provenance_events', 0)}`",
        f"- distinct_threads: `{payload.get('distinct_threads', 0)}`",
        f"- distinct_findings: `{payload.get('distinct_findings', 0)}`",
        f"- detector_fix_candidates: `{len(detector_fix_candidates)}`",
        f"- inspection_candidates: `{len(wrong_thread_candidates) + len(needs_inspection_candidates)}`",
        f"- policy_or_fixture_candidates: `{len(policy_candidates)}`",
        f"- synthetic_smoke_candidates: `{len(smoke_candidates)}`",
        "",
        "## Execution Order",
        "",
        "1. `actionability=fix_detector` 후보만 detector blind spot backlog로 옮깁니다.",
        "2. `wrong_thread_target`은 thread 대상과 expected language를 먼저 확인합니다.",
        "3. `policy_mismatch`는 detector보다 policy나 fixture contract를 먼저 맞춥니다.",
        "4. `synthetic_smoke`는 telemetry loop 검증 이벤트로 보존하되 detector backlog에서는 제외합니다.",
        "5. 수정 후 mixed-language smoke와 telemetry snapshot을 다시 돌려 재발 여부를 확인합니다.",
        "",
    ]

    _append_candidate_section(
        lines,
        title="Detector Fix Candidates",
        candidates=detector_fix_candidates,
        empty_message="(no detector fix candidates above threshold)",
    )

    if not only_actionable:
        _append_candidate_section(
            lines,
            title="Likely Wrong Thread Target",
            candidates=wrong_thread_candidates,
            empty_message="(none)",
        )
        _append_candidate_section(
            lines,
            title="Policy Or Fixture Candidates",
            candidates=policy_candidates,
            empty_message="(none)",
        )
        if show_needs_inspection:
            _append_candidate_section(
                lines,
                title="Needs Inspection",
                candidates=needs_inspection_candidates,
                empty_message="(none)",
            )
        _append_candidate_section(
            lines,
            title="Synthetic Smoke Events",
            candidates=smoke_candidates,
            empty_message="(none)",
        )

    lines.extend(
        [
            "## Raw JSON",
            "",
            "```json",
            json.dumps(payload, indent=2, ensure_ascii=False),
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a prioritized wrong-language detector backlog from review-bot analytics."
    )
    parser.add_argument(
        "--bot-base-url",
        default="http://127.0.0.1:18081",
        help="Base URL for review-bot API.",
    )
    parser.add_argument(
        "--project-ref",
        default=None,
        help="Optional project_ref filter for analytics endpoint.",
    )
    parser.add_argument(
        "--window",
        choices=["14d", "28d"],
        default="28d",
        help="Analytics window to request.",
    )
    parser.add_argument(
        "--min-count",
        type=int,
        default=1,
        help="Minimum triage candidate count to include in the backlog.",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=12,
        help="Maximum number of triage items to emit.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output markdown path. Defaults to docs/baselines/review_bot/wrong_language_backlog_<window>_<date>.md",
    )
    parser.add_argument(
        "--include-smoke",
        action="store_true",
        help="Include smoke candidates in ranked non-smoke sections when their actionability matches.",
    )
    parser.add_argument(
        "--only-actionable",
        action="store_true",
        help="Emit only detector fix candidates and raw JSON.",
    )
    parser.add_argument(
        "--show-needs-inspection",
        action="store_true",
        help="Emit candidates that require manual inspection.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_path = Path(args.output) if args.output else (
        DEFAULT_OUTPUT_DIR
        / f"wrong_language_backlog_{args.window}_{datetime.now(UTC).date().isoformat()}.md"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    report = fetch_json(
        build_url(
            args.bot_base_url,
            "/internal/analytics/wrong-language-feedback",
            project_ref=args.project_ref or "",
            window=args.window,
        )
    )
    output_path.write_text(
        render_markdown(
            bot_base_url=args.bot_base_url,
            project_ref=args.project_ref,
            window=args.window,
            report=report,
            min_count=args.min_count,
            max_items=args.max_items,
            include_smoke=args.include_smoke,
            only_actionable=args.only_actionable,
            show_needs_inspection=args.show_needs_inspection,
        )
        + "\n",
        encoding="utf-8",
    )
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
