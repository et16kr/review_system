from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from review_bot.providers.openai_provider import OpenAIReviewCommentProvider
from review_bot.providers.stub_provider import StubReviewCommentProvider
from review_bot.quality.provider_quality import (
    evaluate_provider_quality,
    load_provider_quality_cases,
    render_markdown_report,
)


def _skipped_openai_report() -> dict[str, object]:
    return {
        "provider": "openai",
        "status": "skipped",
        "skip_reason": "OPENAI_API_KEY is not set",
        "summary": {
            "total_cases": 0,
            "passed_cases": 0,
            "failed_cases": 0,
        },
        "results": [],
    }


def _write_outputs(
    report: dict[str, object],
    *,
    output: str | None,
    json_output: str | None,
) -> None:
    markdown = render_markdown_report(report)
    if output:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown + "\n", encoding="utf-8")
        print(output_path)
    else:
        print(markdown)

    if json_output:
        json_path = Path(json_output)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate review-bot provider draft quality against the golden corpus."
    )
    parser.add_argument(
        "--provider",
        choices=["stub", "openai"],
        default="stub",
        help="Provider to evaluate. OpenAI mode skips cleanly when OPENAI_API_KEY is absent.",
    )
    parser.add_argument(
        "--cases",
        default=None,
        help="Optional provider quality case JSON path.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional Markdown report output path. Defaults to stdout.",
    )
    parser.add_argument(
        "--json-output",
        default=None,
        help="Optional JSON report output path.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.provider == "openai" and not os.environ.get("OPENAI_API_KEY"):
        report = _skipped_openai_report()
        _write_outputs(report, output=args.output, json_output=args.json_output)
        return 0

    cases = load_provider_quality_cases(Path(args.cases) if args.cases else None)
    provider = (
        OpenAIReviewCommentProvider()
        if args.provider == "openai"
        else StubReviewCommentProvider()
    )
    report = evaluate_provider_quality(
        provider=provider,
        cases=cases,
        provider_name=args.provider,
    )
    _write_outputs(report, output=args.output, json_output=args.json_output)
    return 0 if report.get("status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

