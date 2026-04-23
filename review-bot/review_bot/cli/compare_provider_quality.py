from __future__ import annotations

import argparse
import json
from pathlib import Path

from review_bot.quality.provider_quality import (
    build_provider_quality_comparison,
    render_provider_comparison_markdown,
)


def _load_report(path: str) -> dict[str, object]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"provider quality report must be an object: {path}")
    return payload


def _write_outputs(
    report: dict[str, object],
    *,
    output: str | None,
    json_output: str | None,
) -> None:
    markdown = render_provider_comparison_markdown(report)
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
        description="Compare stub and OpenAI provider quality reports."
    )
    parser.add_argument("--stub-json", required=True, help="JSON report from the stub provider.")
    parser.add_argument(
        "--openai-json",
        required=True,
        help="JSON report from the OpenAI provider, including skipped reports.",
    )
    parser.add_argument(
        "--corpus-revision",
        default="packaged-provider-quality-cases",
        help="Corpus revision label to include in the comparison artifact.",
    )
    parser.add_argument(
        "--generated-at",
        default=None,
        help="Optional timestamp override for reproducible tests.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional Markdown comparison output path. Defaults to stdout.",
    )
    parser.add_argument(
        "--json-output",
        default=None,
        help="Optional JSON comparison output path.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    comparison = build_provider_quality_comparison(
        stub_report=_load_report(args.stub_json),
        openai_report=_load_report(args.openai_json),
        generated_at=args.generated_at,
        corpus_revision=args.corpus_revision,
    )
    _write_outputs(comparison, output=args.output, json_output=args.json_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
