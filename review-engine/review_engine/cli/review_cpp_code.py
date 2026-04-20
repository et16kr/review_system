from __future__ import annotations

import argparse
import json
from pathlib import Path

from review_engine.retrieve.search import GuidelineSearchService


def main() -> None:
    parser = argparse.ArgumentParser(description="Review a C++ source file.")
    parser.add_argument("--file", required=True, help="Path to the C++ file.")
    parser.add_argument("--top-k", type=int, default=10, help="Number of results to return.")
    args = parser.parse_args()

    code = Path(args.file).read_text(encoding="utf-8")
    response = GuidelineSearchService().review_code(code, top_k=args.top_k)
    print(json.dumps(response.model_dump(), indent=2))


if __name__ == "__main__":
    main()
