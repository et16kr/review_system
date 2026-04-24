from __future__ import annotations

import argparse
import json
from typing import Literal

from review_engine.config import get_settings
from review_engine.ingest.rule_loader import load_rule_runtime
from review_engine.models import GuidelineRecord, LoadedRuleContext

RuntimeState = Literal["active", "reference", "excluded"]
RUNTIME_STATE_FIELDS: tuple[tuple[RuntimeState, str], ...] = (
    ("active", "active_records"),
    ("reference", "reference_records"),
    ("excluded", "excluded_records"),
)
RUNTIME_STATE_ORDER = {state: index for index, (state, _field) in enumerate(RUNTIME_STATE_FIELDS)}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect rule lifecycle state directly from canonical YAML runtime data."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser(
        "list",
        help="List rules in the selected runtime without reading generated datasets.",
    )
    _add_runtime_args(list_parser)
    list_parser.add_argument(
        "--state",
        choices=["all", "active", "reference", "excluded"],
        default="all",
        help="Optional runtime state filter.",
    )
    list_parser.add_argument(
        "--pack-id",
        default=None,
        help="Optional pack filter after runtime selection.",
    )
    list_parser.set_defaults(handler=_handle_list)

    show_parser = subparsers.add_parser(
        "show",
        help="Show one rule from the selected runtime without reading generated datasets.",
    )
    _add_runtime_args(show_parser)
    show_parser.add_argument("--rule", required=True, help="Rule number to inspect.")
    show_parser.add_argument(
        "--pack-id",
        default=None,
        help="Optional pack filter to disambiguate duplicate rule numbers.",
    )
    show_parser.set_defaults(handler=_handle_show)
    return parser


def _add_runtime_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--language-id", default=None, help="Optional explicit language override.")
    parser.add_argument("--profile-id", default=None, help="Optional explicit profile override.")
    parser.add_argument("--context-id", default=None, help="Optional explicit context override.")
    parser.add_argument("--dialect-id", default=None, help="Optional explicit dialect override.")
    parser.add_argument(
        "--all-packs",
        action="store_true",
        help=(
            "Inspect every pack for the selected language instead of the "
            "profile-selected runtime only."
        ),
    )


def _handle_list(args: argparse.Namespace) -> dict[str, object]:
    runtime = _load_runtime(args)
    rules = [
        _serialize_list_item(record, runtime_state=runtime_state)
        for runtime_state, record in _iter_runtime_records(
            runtime,
            state_filter=args.state,
            pack_id=args.pack_id,
        )
    ]
    return {
        **_serialize_runtime(runtime),
        "state_filter": args.state,
        "pack_id_filter": args.pack_id,
        "rules": rules,
    }


def _handle_show(args: argparse.Namespace) -> dict[str, object]:
    runtime = _load_runtime(args)
    matches = [
        (runtime_state, record)
        for runtime_state, record in _iter_runtime_records(
            runtime,
            state_filter="all",
            pack_id=args.pack_id,
        )
        if record.rule_no == args.rule
    ]
    if not matches:
        raise SystemExit(f"Rule not found in selected runtime: {args.rule}")
    if len(matches) > 1:
        candidate_packs = ", ".join(sorted({record.pack_id or "" for _state, record in matches}))
        raise SystemExit(
            "Multiple rules matched "
            f"{args.rule}; provide --pack-id to disambiguate: {candidate_packs}"
        )

    runtime_state, record = matches[0]
    return {
        **_serialize_runtime(runtime),
        "rule": _serialize_rule(record, runtime_state=runtime_state),
    }


def _load_runtime(args: argparse.Namespace) -> LoadedRuleContext:
    return load_rule_runtime(
        get_settings(),
        language_id=args.language_id,
        profile_id=args.profile_id,
        context_id=args.context_id,
        dialect_id=args.dialect_id,
        include_all_packs=args.all_packs,
    )


def _iter_runtime_records(
    runtime: LoadedRuleContext,
    *,
    state_filter: str,
    pack_id: str | None,
) -> list[tuple[RuntimeState, GuidelineRecord]]:
    collected: list[tuple[RuntimeState, GuidelineRecord]] = []
    for runtime_state, field_name in RUNTIME_STATE_FIELDS:
        if state_filter != "all" and runtime_state != state_filter:
            continue
        for record in getattr(runtime, field_name):
            if pack_id and record.pack_id != pack_id:
                continue
            collected.append((runtime_state, record))
    collected.sort(
        key=lambda item: (
            RUNTIME_STATE_ORDER[item[0]],
            item[1].rule_no,
            item[1].pack_id or "",
            item[1].context_id or "",
            item[1].dialect_id or "",
        )
    )
    return collected


def _serialize_runtime(runtime: LoadedRuleContext) -> dict[str, object]:
    return {
        "source_of_truth": "canonical_yaml",
        "language_id": runtime.language_id,
        "profile_id": runtime.profile.profile_id,
        "context_id": runtime.context_id,
        "dialect_id": runtime.dialect_id,
        "selected_pack_ids": runtime.selected_pack_ids,
        "shared_pack_ids": runtime.shared_pack_ids,
        "public_rule_root": runtime.public_rule_root,
        "extension_rule_roots": runtime.extension_rule_roots,
    }


def _serialize_list_item(
    record: GuidelineRecord,
    *,
    runtime_state: RuntimeState,
) -> dict[str, object]:
    return {
        "rule_no": record.rule_no,
        "rule_uid": record.rule_uid,
        "title": record.title,
        "pack_id": record.pack_id,
        "runtime_state": runtime_state,
        "reviewability": record.reviewability,
        "priority_tier": record.priority_tier,
        "conflict_action": record.conflict_action,
        "source_path": record.source,
        "context_id": record.context_id,
        "dialect_id": record.dialect_id,
    }


def _serialize_rule(record: GuidelineRecord, *, runtime_state: RuntimeState) -> dict[str, object]:
    payload = record.model_dump()
    payload["runtime_state"] = runtime_state
    payload["source_path"] = payload.pop("source")
    return payload


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)
    payload = args.handler(args)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
