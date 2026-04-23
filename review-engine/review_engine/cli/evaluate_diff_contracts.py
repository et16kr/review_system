from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from review_engine.config import get_settings
from review_engine.retrieve.search import GuidelineSearchService


def _resolve_repo_path(path_value: str, *, project_root: Path) -> Path:
    path = Path(path_value)
    if path.is_absolute() or path.exists():
        return path
    return project_root / path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate bundled diff contract examples against expected rules.",
    )
    parser.add_argument(
        "--spec",
        default="examples/cpp_diff_contracts.json",
        help="Path to the diff contract specification JSON file.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=8,
        help="Number of retrieval results to inspect per diff.",
    )
    args = parser.parse_args()

    settings = get_settings()
    spec_path = _resolve_repo_path(args.spec, project_root=settings.project_root)
    cases = json.loads(spec_path.read_text(encoding="utf-8"))
    service = GuidelineSearchService(settings)
    report: list[dict[str, object]] = []

    for case in cases:
        example_path = _resolve_repo_path(
            str(case["example_path"]),
            project_root=settings.project_root,
        )
        payload = example_path.read_text(encoding="utf-8")
        response = service.review_diff(
            payload,
            top_k=args.top_k,
            file_path=str(case.get("source_path") or case["example_path"]),
        )
        returned_rules = [result.rule_no for result in response.results]
        expected_rules = list(case.get("expected_rules", []))
        matched_rules = [rule_no for rule_no in expected_rules if rule_no in returned_rules]
        missing_rules = [rule_no for rule_no in expected_rules if rule_no not in returned_rules]
        report.append(
            {
                "example_path": str(example_path),
                "focus_patterns": list(case.get("focus_patterns", [])),
                "expected_rules": expected_rules,
                "matched_rules": matched_rules,
                "missing_rules": missing_rules,
                "returned_rules": returned_rules,
                "passed": not missing_rules,
            }
        )

    summary = {
        "spec": str(spec_path),
        "top_k": args.top_k,
        "passed": sum(1 for item in report if item["passed"]),
        "failed": sum(1 for item in report if not item["passed"]),
        "cases": report,
    }
    print(json.dumps(summary, indent=2))
    if summary["failed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
