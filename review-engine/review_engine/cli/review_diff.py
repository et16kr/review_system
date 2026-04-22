from __future__ import annotations

import argparse
import json
from pathlib import Path

from review_engine.retrieve.search import GuidelineSearchService


def main() -> None:
    parser = argparse.ArgumentParser(description="Review a diff with language-aware rule selection.")
    parser.add_argument("--diff", required=True, help="Diff file to review.")
    parser.add_argument("--file-path", default=None, help="Optional logical file path for language inference.")
    parser.add_argument("--top-k", type=int, default=10, help="Number of top results to return.")
    parser.add_argument("--language-id", default=None, help="Optional explicit language override.")
    parser.add_argument("--profile-id", default=None, help="Optional explicit profile override.")
    parser.add_argument("--context-id", default=None, help="Optional explicit context override.")
    parser.add_argument("--dialect-id", default=None, help="Optional explicit dialect override.")
    args = parser.parse_args()

    diff_path = Path(args.diff)
    response = GuidelineSearchService().review_diff(
        diff_path.read_text(encoding="utf-8"),
        top_k=args.top_k,
        file_path=args.file_path,
        language_id=args.language_id,
        profile_id=args.profile_id,
        context_id=args.context_id,
        dialect_id=args.dialect_id,
    )
    print(json.dumps(response.model_dump(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
