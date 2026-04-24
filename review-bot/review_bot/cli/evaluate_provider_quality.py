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

DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_OPENAI_MODEL = "gpt-4o"


def _provider_runtime(provider_name: str) -> dict[str, object]:
    if provider_name == "stub":
        return {
            "configured_provider": "stub",
            "effective_provider": "stub",
            "fallback_used": False,
            "transport_class": "deterministic_stub",
        }

    base_url = (
        str(os.getenv("BOT_OPENAI_BASE_URL", "") or "").strip().rstrip("/")
        or DEFAULT_OPENAI_BASE_URL
    )
    transport_class = (
        "default_openai_base_url"
        if base_url == DEFAULT_OPENAI_BASE_URL
        else "non_default_openai_compatible_base_url"
    )
    return {
        "configured_provider": "openai",
        "effective_provider": "openai",
        "fallback_used": False,
        "configured_model": os.getenv("BOT_OPENAI_MODEL", DEFAULT_OPENAI_MODEL),
        "endpoint_base_url": base_url,
        "transport_class": transport_class,
    }


def _skipped_openai_report(provider_runtime: dict[str, object]) -> dict[str, object]:
    return {
        "provider": "openai",
        "status": "skipped",
        "skip_reason": "OPENAI_API_KEY is not set",
        "provider_runtime": provider_runtime,
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
    provider_runtime = _provider_runtime(args.provider)
    if args.provider == "openai" and not os.environ.get("OPENAI_API_KEY"):
        report = _skipped_openai_report(provider_runtime)
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
        provider_runtime=provider_runtime,
    )
    _write_outputs(report, output=args.output, json_output=args.json_output)
    return 0 if report.get("status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
