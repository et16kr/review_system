from __future__ import annotations

import argparse
import json

from review_engine.retrieve.search import GuidelineSearchService


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest the canonical public C++ rule root and optional extensions.",
    )
    parser.add_argument("--force-refresh", action="store_true", help="Refresh cached HTML source.")
    args = parser.parse_args()

    summary = GuidelineSearchService().ingest(force_refresh=args.force_refresh)
    print(json.dumps(summary.model_dump(), indent=2))


if __name__ == "__main__":
    main()
