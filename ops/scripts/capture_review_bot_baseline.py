#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib import error, parse, request

ROOT = Path("/home/et16/work/review_system")
DEFAULT_OUTPUT_DIR = ROOT / "docs" / "baselines" / "review_bot"
METRIC_PREFIXES = (
    "findings_published_total",
    "findings_suppressed_total",
    "findings_resolved_total",
    "feedback_commands_total",
    "verify_attempts_total",
    "verify_dropped_total",
    "finding_resolution_events_total",
)


def fetch_json(url: str) -> dict | list:
    with request.urlopen(url, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_optional_json(url: str) -> dict | list:
    try:
        return fetch_json(url)
    except error.HTTPError as exc:
        return {
            "available": False,
            "error": f"HTTP {exc.code}",
            "url": url,
        }
    except error.URLError as exc:
        return {
            "available": False,
            "error": str(exc.reason),
            "url": url,
        }


def fetch_text(url: str) -> str:
    with request.urlopen(url, timeout=20) as response:
        return response.read().decode("utf-8")


def build_url(base_url: str, path: str, **params: str) -> str:
    filtered = {key: value for key, value in params.items() if value}
    query = parse.urlencode(filtered)
    return f"{base_url.rstrip('/')}{path}" + (f"?{query}" if query else "")


def select_metric_lines(metrics_text: str) -> list[str]:
    lines: list[str] = []
    for raw_line in metrics_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if any(line.startswith(prefix) for prefix in METRIC_PREFIXES):
            lines.append(line)
    return lines


def render_markdown(
    *,
    baseline_kind: str,
    bot_base_url: str,
    project_ref: str | None,
    source_family: str | None,
    health: dict | list,
    rule_effectiveness: dict | list,
    finding_outcomes_14d: dict | list,
    finding_outcomes_28d: dict | list,
    wrong_language_feedback_28d: dict | list,
    metric_lines: list[str],
) -> str:
    generated_at = datetime.now(UTC).isoformat()
    lines = [
        f"# Review Bot {baseline_kind.upper()} Baseline",
        "",
        f"- generated_at_utc: `{generated_at}`",
        f"- bot_base_url: `{bot_base_url}`",
        f"- project_ref: `{project_ref or 'all'}`",
        f"- source_family: `{source_family or 'all'}`",
        "",
        "## Health",
        "",
        "```json",
        json.dumps(health, indent=2, ensure_ascii=False),
        "```",
        "",
        "## Rule Effectiveness",
        "",
        "```json",
        json.dumps(rule_effectiveness, indent=2, ensure_ascii=False),
        "```",
        "",
        "## Finding Outcomes 14d",
        "",
        "```json",
        json.dumps(finding_outcomes_14d, indent=2, ensure_ascii=False),
        "```",
        "",
        "## Finding Outcomes 28d",
        "",
        "```json",
        json.dumps(finding_outcomes_28d, indent=2, ensure_ascii=False),
        "```",
        "",
        "## Wrong-Language Feedback 28d",
        "",
        "```json",
        json.dumps(wrong_language_feedback_28d, indent=2, ensure_ascii=False),
        "```",
        "",
        "## Selected Metrics Snapshot",
        "",
        "```text",
    ]
    lines.extend(metric_lines or ["(no matching metric lines found)"])
    lines.extend(
        [
            "```",
            "",
            "## Notes",
            "",
            "- `baseline_v0`는 instrumentation bootstrap 또는 cutover 직후 스냅샷 용도다.",
            "- `baseline_v1`는 새 verify/lifecycle analytics가 충분한 14d/28d window를 채운 뒤 기록한다.",
            "- `finding-outcomes`가 404 또는 연결 실패라면, 아직 새 Phase A 경로가 배포되지 않았다는 뜻으로 해석한다.",
        ]
    )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture a markdown baseline snapshot from review-bot analytics endpoints."
    )
    parser.add_argument(
        "--bot-base-url",
        default="http://127.0.0.1:18081",
        help="Base URL for review-bot API.",
    )
    parser.add_argument(
        "--baseline-kind",
        choices=["v0", "v1"],
        default="v0",
        help="Baseline document kind to generate.",
    )
    parser.add_argument(
        "--project-ref",
        default=None,
        help="Optional project_ref filter for analytics endpoints.",
    )
    parser.add_argument(
        "--source-family",
        default=None,
        help="Optional source_family filter for analytics endpoints.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output markdown path. Defaults to docs/baselines/review_bot/baseline_<kind>_<date>.md",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_path = Path(args.output) if args.output else (
        DEFAULT_OUTPUT_DIR
        / f"baseline_{args.baseline_kind}_{datetime.now(UTC).date().isoformat()}.md"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    health = fetch_json(build_url(args.bot_base_url, "/health"))
    rule_effectiveness = fetch_json(
        build_url(args.bot_base_url, "/internal/analytics/rule-effectiveness")
    )
    outcomes_14d = fetch_optional_json(
        build_url(
            args.bot_base_url,
            "/internal/analytics/finding-outcomes",
            window="14d",
            project_ref=args.project_ref or "",
            source_family=args.source_family or "",
        )
    )
    outcomes_28d = fetch_optional_json(
        build_url(
            args.bot_base_url,
            "/internal/analytics/finding-outcomes",
            window="28d",
            project_ref=args.project_ref or "",
            source_family=args.source_family or "",
        )
    )
    wrong_language_28d = fetch_optional_json(
        build_url(
            args.bot_base_url,
            "/internal/analytics/wrong-language-feedback",
            window="28d",
            project_ref=args.project_ref or "",
        )
    )
    metrics_text = fetch_text(build_url(args.bot_base_url, "/metrics"))
    markdown = render_markdown(
        baseline_kind=args.baseline_kind,
        bot_base_url=args.bot_base_url,
        project_ref=args.project_ref,
        source_family=args.source_family,
        health=health,
        rule_effectiveness=rule_effectiveness,
        finding_outcomes_14d=outcomes_14d,
        finding_outcomes_28d=outcomes_28d,
        wrong_language_feedback_28d=wrong_language_28d,
        metric_lines=select_metric_lines(metrics_text),
    )
    output_path.write_text(markdown, encoding="utf-8")
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
