from __future__ import annotations

import argparse
import json
from pathlib import Path

from review_bot.quality.review_unit_split_audit import (
    evaluate_review_unit_split_cases,
    load_review_unit_split_cases,
    render_markdown_report,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Audit current fixed-line review unit split behavior"
            " on the deterministic corpus."
        )
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


def _write_output(text: str, *, output: str | None) -> None:
    if output is None:
        print(text)
        return
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text + "\n", encoding="utf-8")
    print(output_path)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = evaluate_review_unit_split_cases(load_review_unit_split_cases())
    _write_output(render_markdown_report(report), output=args.output)
    if args.json_output:
        json_path = Path(args.json_output)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
