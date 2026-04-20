from __future__ import annotations

import argparse
import json

from review_engine.retrieve.search import GuidelineSearchService


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect a guideline rule.")
    parser.add_argument("--rule", required=True, help="Rule number to inspect.")
    args = parser.parse_args()

    rule = GuidelineSearchService().inspect_rule(args.rule)
    if rule is None:
        raise SystemExit(f"Rule not found: {args.rule}")
    print(json.dumps(rule.model_dump(), indent=2))


if __name__ == "__main__":
    main()
