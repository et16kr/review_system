from __future__ import annotations

import argparse
import json
from pathlib import Path

from review_engine.rule_package import (
    RulePackageValidationError,
    validate_rule_package,
    validate_rule_package_split_gate,
)


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

    split_gate_parser = subparsers.add_parser(
        "split-gate",
        help="Run the read-only private/public split validation gate for a rule package.",
    )
    split_gate_parser.add_argument(
        "--package-root",
        required=True,
        type=Path,
        help="Path to the private rule package root containing package.yaml.",
    )
    split_gate_parser.add_argument(
        "--manifest-name",
        default="package.yaml",
        help="Package manifest filename relative to --package-root.",
    )
    split_gate_parser.add_argument(
        "--private-artifact-root",
        type=Path,
        default=None,
        help="Base directory for private validation artifacts.",
    )
    split_gate_parser.set_defaults(handler=_handle_split_gate)
    return parser


def _handle_validate(args: argparse.Namespace) -> dict[str, object]:
    return {
        "command": "validate",
        **validate_rule_package(
            args.package_root,
            manifest_name=args.manifest_name,
        ),
    }


def _handle_split_gate(args: argparse.Namespace) -> dict[str, object]:
    return {
        "command": "split-gate",
        **validate_rule_package_split_gate(
            args.package_root,
            manifest_name=args.manifest_name,
            private_artifact_root=args.private_artifact_root,
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
