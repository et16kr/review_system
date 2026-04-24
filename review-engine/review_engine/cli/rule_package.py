from __future__ import annotations

import argparse
import json
from pathlib import Path

from review_engine.rule_package import RulePackageValidationError, validate_rule_package


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate private rule package metadata without mutating runtime artifacts."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate package.yaml and its runtime extension root boundary.",
    )
    validate_parser.add_argument(
        "--package-root",
        required=True,
        type=Path,
        help="Path to the private rule package root containing package.yaml.",
    )
    validate_parser.add_argument(
        "--manifest-name",
        default="package.yaml",
        help="Package manifest filename relative to --package-root.",
    )
    validate_parser.set_defaults(handler=_handle_validate)
    return parser


def _handle_validate(args: argparse.Namespace) -> dict[str, object]:
    return {
        "command": "validate",
        **validate_rule_package(
            args.package_root,
            manifest_name=args.manifest_name,
        ),
    }


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        payload = args.handler(args)
    except RulePackageValidationError as exc:
        raise SystemExit(f"Package validation failed: {exc}") from exc
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
