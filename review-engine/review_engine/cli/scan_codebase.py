from __future__ import annotations

import argparse
import json
from pathlib import Path

from review_engine.config import write_json_file
from review_engine.query.repository_scan import render_repo_scan_markdown, scan_repository


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scan a C/C++ codebase for likely public guideline patterns."
    )
    parser.add_argument("--root", required=True, help="Repository or source root to scan.")
    parser.add_argument(
        "--include-dir",
        action="append",
        default=[],
        help="Top-level directory under root to include. Can be repeated.",
    )
    parser.add_argument(
        "--exclude-dir",
        action="append",
        default=[],
        help="Directory name to exclude. Can be repeated.",
    )
    parser.add_argument(
        "--exclude-fragment",
        action="append",
        default=[],
        help="Path fragment to exclude anywhere in the file path. Can be repeated.",
    )
    parser.add_argument(
        "--ignore-pattern",
        action="append",
        default=[],
        help="Pattern name to ignore in the scan summary. Can be repeated.",
    )
    parser.add_argument(
        "--top-files",
        type=int,
        default=30,
        help="Files to keep in markdown output.",
    )
    parser.add_argument(
        "--json-output",
        help="Optional path to write the full JSON scan report.",
    )
    parser.add_argument(
        "--markdown-output",
        help="Optional path to write a markdown summary report.",
    )
    args = parser.parse_args()

    report = scan_repository(
        Path(args.root),
        include_dirs=args.include_dir,
        exclude_dirs=args.exclude_dir,
        exclude_fragments=args.exclude_fragment,
        ignore_patterns=args.ignore_pattern,
    )

    if args.json_output:
        write_json_file(Path(args.json_output), report.model_dump())

    if args.markdown_output:
        markdown = render_repo_scan_markdown(report, top_files=args.top_files)
        Path(args.markdown_output).write_text(markdown, encoding="utf-8")

    summary = {
        "root": report.root,
        "scanned_files": report.scanned_files,
        "matched_files": report.matched_files,
        "top_patterns": dict(list(report.aggregate_patterns.items())[:12]),
        "top_files": [
            {
                "path": finding.path,
                "score": finding.score,
                "pattern_count": finding.pattern_count,
                "patterns": [pattern.name for pattern in finding.patterns[:6]],
            }
            for finding in report.findings[: args.top_files]
        ],
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
