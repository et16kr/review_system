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
        description="Evaluate retrieval quality against example expectations."
    )
    parser.add_argument(
        "--spec",
        default="examples/expected_retrieval_examples.json",
        help="Path to the expectation JSON file.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=12,
        help="Number of results to inspect per example.",
    )
    args = parser.parse_args()

    settings = get_settings()
    spec_path = _resolve_repo_path(args.spec, project_root=settings.project_root)
    cases = json.loads(spec_path.read_text(encoding="utf-8"))
    service = GuidelineSearchService(settings)
    report: list[dict[str, object]] = []

    for case in cases:
        input_path = _resolve_repo_path(str(case["input"]), project_root=settings.project_root)
        review_path = case.get("review_path") or case.get("source_path")
        payload = input_path.read_text(encoding="utf-8")
        if input_path.suffix == ".diff":
            kwargs = {"file_path": str(review_path)} if review_path else {}
            response = service.review_diff(payload, top_k=args.top_k, **kwargs)
        else:
            response = service.review_code(
                payload,
                top_k=args.top_k,
                file_path=str(review_path or case["input"]),
            )

        returned_rules = [result.rule_no for result in response.results]
        expected_rules = list(case["expected_rules"])
        matched_rules = [rule_no for rule_no in expected_rules if rule_no in returned_rules]
        missing_rules = [rule_no for rule_no in expected_rules if rule_no not in returned_rules]
        report.append(
            {
                "input": str(input_path),
                "expected_rules": expected_rules,
                "matched_rules": matched_rules,
                "missing_rules": missing_rules,
                "returned_rules": returned_rules,
                "passed": not missing_rules,
            }
        )

    summary = {
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
