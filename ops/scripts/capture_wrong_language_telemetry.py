#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib import parse, request

ROOT = Path("/home/et16/work/review_system")
DEFAULT_OUTPUT_DIR = ROOT / "docs" / "baselines" / "review_bot"


def fetch_json(url: str) -> dict | list:
    with request.urlopen(url, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def build_url(base_url: str, path: str, **params: str) -> str:
    filtered = {key: value for key, value in params.items() if value}
    query = parse.urlencode(filtered)
    return f"{base_url.rstrip('/')}{path}" + (f"?{query}" if query else "")


def _markdown_table(headers: list[str], rows: list[list[str]]) -> list[str]:
    if not rows:
        return ["(no data)"]
    header_line = "| " + " | ".join(headers) + " |"
    divider_line = "| " + " | ".join("---" for _ in headers) + " |"
    body_lines = ["| " + " | ".join(row) + " |" for row in rows]
    return [header_line, divider_line, *body_lines]


def render_markdown(
    *,
    bot_base_url: str,
    project_ref: str | None,
    window: str,
    report: dict | list,
) -> str:
    generated_at = datetime.now(UTC).isoformat()
    payload = report if isinstance(report, dict) else {}
    smoke_events = int(payload.get("smoke_events") or 0)
    smoke_candidates = [
        item
        for item in payload.get("triage_candidates", [])
        if str(item.get("provenance") or "unknown") == "smoke"
        or str(item.get("triage_cause") or "needs_inspection") == "synthetic_smoke"
        or str(item.get("actionability") or "inspect_thread")
        == "ignore_for_detector_backlog"
    ]
    lines = [
        "# Review Bot Wrong-Language Telemetry",
        "",
        f"- generated_at_utc: `{generated_at}`",
        f"- bot_base_url: `{bot_base_url}`",
        f"- project_ref: `{project_ref or 'all'}`",
        f"- window: `{window}`",
        "",
        "## Summary",
        "",
        f"- total_events: `{payload.get('total_events', 0)}`",
        f"- smoke_events: `{payload.get('smoke_events', 0)}`",
        f"- production_events: `{payload.get('production_events', 0)}`",
        f"- unknown_provenance_events: `{payload.get('unknown_provenance_events', 0)}`",
        f"- distinct_threads: `{payload.get('distinct_threads', 0)}`",
        f"- distinct_findings: `{payload.get('distinct_findings', 0)}`",
        "",
    ]
    if smoke_events > 0 or smoke_candidates:
        lines.extend(
            [
                "## Interpretation Note",
                "",
                (
                    "Smoke provenance가 포함되어 있습니다. 이 항목은 telemetry loop 검증용으로 "
                    "보존하되 detector backlog로 바로 옮기지 마세요."
                ),
                "",
            ]
        )
    lines.extend(["## Top Language Pairs", ""])
    lines.extend(
        _markdown_table(
            ["detected", "expected", "count"],
            [
                [
                    str(item.get("detected_language_id") or "unknown"),
                    str(item.get("expected_language_id") or "unknown"),
                    str(item.get("count") or 0),
                ]
                for item in payload.get("top_language_pairs", [])
            ],
        )
    )
    lines.extend(
        [
            "",
            "## Top Profiles",
            "",
        ]
    )
    lines.extend(
        _markdown_table(
            ["detected", "expected", "profile", "context", "count"],
            [
                [
                    str(item.get("detected_language_id") or "unknown"),
                    str(item.get("expected_language_id") or "unknown"),
                    str(item.get("profile_id") or "default"),
                    str(item.get("context_id") or "generic"),
                    str(item.get("count") or 0),
                ]
                for item in payload.get("top_profiles", [])
            ],
        )
    )
    lines.extend(
        [
            "",
            "## Top Paths",
            "",
        ]
    )
    lines.extend(
        _markdown_table(
            ["detected", "expected", "path_pattern", "count"],
            [
                [
                    str(item.get("detected_language_id") or "unknown"),
                    str(item.get("expected_language_id") or "unknown"),
                    str(item.get("path_pattern") or "<unknown>"),
                    str(item.get("count") or 0),
                ]
                for item in payload.get("top_paths", [])
            ],
        )
    )
    lines.extend(
        [
            "",
            "## Triage Candidates",
            "",
        ]
    )
    lines.extend(
        _markdown_table(
            [
                "priority",
                "provenance",
                "triage_cause",
                "actionability",
                "detected",
                "expected",
                "profile",
                "context",
                "path_pattern",
                "count",
                "suggested_action",
            ],
            [
                [
                    str(item.get("priority") or "low"),
                    str(item.get("provenance") or "unknown"),
                    str(item.get("triage_cause") or "needs_inspection"),
                    str(item.get("actionability") or "inspect_thread"),
                    str(item.get("detected_language_id") or "unknown"),
                    str(item.get("expected_language_id") or "unknown"),
                    str(item.get("profile_id") or "default"),
                    str(item.get("context_id") or "generic"),
                    str(item.get("path_pattern") or "<unknown>"),
                    str(item.get("count") or 0),
                    str(item.get("suggested_action") or ""),
                ]
                for item in payload.get("triage_candidates", [])
            ],
        )
    )
    lines.extend(
        [
            "",
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
        description="Capture wrong-language telemetry from review-bot and render it as markdown."
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
        "--output",
        default=None,
        help="Output markdown path. Defaults to docs/baselines/review_bot/wrong_language_<window>_<date>.md",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_path = Path(args.output) if args.output else (
        DEFAULT_OUTPUT_DIR
        / f"wrong_language_{args.window}_{datetime.now(UTC).date().isoformat()}.md"
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
        )
        + "\n",
        encoding="utf-8",
    )
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
