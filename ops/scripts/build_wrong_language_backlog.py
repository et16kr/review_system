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


def render_markdown(
    *,
    bot_base_url: str,
    project_ref: str | None,
    window: str,
    report: dict | list,
    min_count: int,
    max_items: int,
) -> str:
    generated_at = datetime.now(UTC).isoformat()
    payload = report if isinstance(report, dict) else {}
    candidates = [
        item
        for item in payload.get("triage_candidates", [])
        if int(item.get("count") or 0) >= min_count
    ]
    candidates = sorted(
        candidates,
        key=lambda item: (
            PRIORITY_ORDER.get(str(item.get("priority") or "low"), 99),
            -int(item.get("count") or 0),
            str(item.get("detected_language_id") or ""),
            str(item.get("expected_language_id") or ""),
            str(item.get("path_pattern") or ""),
        ),
    )[:max_items]

    lines = [
        "# Review Bot Wrong-Language Backlog",
        "",
        f"- generated_at_utc: `{generated_at}`",
        f"- bot_base_url: `{bot_base_url}`",
        f"- project_ref: `{project_ref or 'all'}`",
        f"- window: `{window}`",
        f"- min_count: `{min_count}`",
        f"- max_items: `{max_items}`",
        "",
        "## Summary",
        "",
        f"- total_events: `{payload.get('total_events', 0)}`",
        f"- distinct_threads: `{payload.get('distinct_threads', 0)}`",
        f"- distinct_findings: `{payload.get('distinct_findings', 0)}`",
        f"- backlog_items: `{len(candidates)}`",
        "",
        "## Execution Order",
        "",
        "1. `high` priority pair/path/profile 조합부터 detector blind spot을 수정합니다.",
        "2. 같은 pair가 특정 `profile/context`에 몰리면 registry와 prompt routing을 함께 봅니다.",
        "3. 같은 pair가 `docs`나 `.github/workflows` 같은 경로 버킷에 몰리면 path classification을 먼저 조정합니다.",
        "4. 수정 후 mixed-language smoke와 telemetry snapshot을 다시 돌려 재발 여부를 확인합니다.",
        "",
    ]

    if not candidates:
        lines.extend(
            [
                "## Prioritized Items",
                "",
                "(no backlog items above threshold)",
                "",
            ]
        )
    else:
        for priority in ("high", "medium", "low"):
            grouped = [item for item in candidates if str(item.get("priority") or "low") == priority]
            lines.extend([f"## {priority.title()} Priority", ""])
            if not grouped:
                lines.extend(["(none)", ""])
                continue
            for index, item in enumerate(grouped, start=1):
                profile_id = str(item.get("profile_id") or "default")
                context_id = str(item.get("context_id") or "generic")
                path_pattern = str(item.get("path_pattern") or "<unknown>")
                suggested_action = str(item.get("suggested_action") or "")
                lines.extend(
                    [
                        f"### {index}. {_format_candidate_title(item)}",
                        "",
                        f"- profile/context: `{profile_id}` / `{context_id}`",
                        f"- path_pattern: `{path_pattern}`",
                        f"- suggested_action: {suggested_action}",
                        "",
                    ]
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
        )
        + "\n",
        encoding="utf-8",
    )
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
