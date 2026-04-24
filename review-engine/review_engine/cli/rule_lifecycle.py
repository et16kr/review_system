from __future__ import annotations

import argparse
import json
import shlex
from collections.abc import Iterable
from pathlib import Path
from typing import Literal

from review_engine.config import Settings, get_settings
from review_engine.ingest.rule_loader import load_rule_runtime, load_rule_runtime_selection
from review_engine.models import GuidelineRecord, LoadedRuleContext, RuleEntry, RulePackManifest

RuntimeState = Literal["active", "reference", "excluded", "disabled"]
MutationAction = Literal["enable", "disable"]
RUNTIME_STATE_FIELDS: tuple[tuple[RuntimeState, str], ...] = (
    ("active", "active_records"),
    ("reference", "reference_records"),
    ("excluded", "excluded_records"),
)
RUNTIME_STATE_ORDER = {
    state: index for index, state in enumerate(("active", "reference", "excluded", "disabled"))
}


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
        choices=["all", "active", "reference", "excluded", "disabled"],
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

    disable_parser = subparsers.add_parser(
        "disable",
        help="Disable one canonical YAML rule entry in the selected runtime.",
    )
    _add_runtime_args(disable_parser)
    disable_parser.add_argument("--rule", required=True, help="Rule number to disable.")
    disable_parser.add_argument(
        "--pack-id",
        default=None,
        help="Optional pack filter to disambiguate duplicate rule numbers.",
    )
    disable_parser.set_defaults(handler=_handle_disable)

    enable_parser = subparsers.add_parser(
        "enable",
        help="Enable one canonical YAML rule entry in the selected runtime.",
    )
    _add_runtime_args(enable_parser)
    enable_parser.add_argument("--rule", required=True, help="Rule number to enable.")
    enable_parser.add_argument(
        "--pack-id",
        default=None,
        help="Optional pack filter to disambiguate duplicate rule numbers.",
    )
    enable_parser.set_defaults(handler=_handle_enable)
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
    _settings, runtime, selected_pack_index = _load_runtime_selection(args)
    rules = [
        _serialize_list_item(record, runtime_state=runtime_state)
        for runtime_state, record in _iter_inspection_records(
            runtime,
            selected_pack_index=selected_pack_index,
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
    _settings, runtime, selected_pack_index = _load_runtime_selection(args)
    matches = [
        (runtime_state, record)
        for runtime_state, record in _iter_inspection_records(
            runtime,
            selected_pack_index=selected_pack_index,
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


def _handle_disable(args: argparse.Namespace) -> dict[str, object]:
    return _handle_mutation(args, action="disable")


def _handle_enable(args: argparse.Namespace) -> dict[str, object]:
    return _handle_mutation(args, action="enable")


def _load_runtime(args: argparse.Namespace) -> LoadedRuleContext:
    return load_rule_runtime(
        get_settings(),
        language_id=args.language_id,
        profile_id=args.profile_id,
        context_id=args.context_id,
        dialect_id=args.dialect_id,
        include_all_packs=args.all_packs,
    )


def _load_runtime_selection(
    args: argparse.Namespace,
) -> tuple[Settings, LoadedRuleContext, dict[str, tuple[RulePackManifest, Path]]]:
    settings = get_settings()
    runtime, selected_pack_index = load_rule_runtime_selection(
        settings,
        language_id=args.language_id,
        profile_id=args.profile_id,
        context_id=args.context_id,
        dialect_id=args.dialect_id,
        include_all_packs=args.all_packs,
    )
    return settings, runtime, selected_pack_index


def _handle_mutation(
    args: argparse.Namespace,
    *,
    action: MutationAction,
) -> dict[str, object]:
    settings, runtime, selected_pack_index = _load_runtime_selection(args)
    pack_id, pack_source_path, previous_enabled = _find_mutation_target(
        rule_no=args.rule,
        pack_id=args.pack_id,
        selected_pack_index=selected_pack_index,
    )
    _assert_within_write_boundary(
        pack_source_path,
        settings=settings,
        runtime=runtime,
    )
    updated_enabled = action == "enable"
    changed = _set_pack_entry_enabled(
        path=pack_source_path,
        rule_no=args.rule,
        enabled=updated_enabled,
    )
    return {
        **_serialize_runtime(runtime),
        "command": action,
        "rule_no": args.rule,
        "pack_id": pack_id,
        "source_path": str(pack_source_path),
        "write_boundary": "canonical_pack_yaml",
        "previous_enabled": previous_enabled,
        "updated_enabled": updated_enabled,
        "changed": changed,
        "validation_plan": _build_mutation_validation_plan(
            runtime=runtime,
            rule_no=args.rule,
            pack_id=pack_id,
            include_all_packs=args.all_packs,
        ),
    }


def _build_mutation_validation_plan(
    *,
    runtime: LoadedRuleContext,
    rule_no: str,
    pack_id: str,
    include_all_packs: bool,
) -> dict[str, object]:
    runtime_args = _build_runtime_selector_args(
        runtime=runtime,
        include_all_packs=include_all_packs,
    )
    return {
        "scope": "rule_lifecycle_mutation",
        "source_of_truth": "canonical_yaml",
        "runtime_selector": {
            "language_id": runtime.language_id,
            "profile_id": runtime.profile.profile_id,
            "context_id": runtime.context_id,
            "dialect_id": runtime.dialect_id,
            "all_packs": include_all_packs,
            "pack_id": pack_id,
            "selected_pack_ids": runtime.selected_pack_ids,
        },
        "commands": [
            {
                "name": "show_rule",
                "command": _shell_join(
                    [
                        "uv",
                        "run",
                        "--project",
                        "review-engine",
                        "python",
                        "-m",
                        "review_engine.cli.rule_lifecycle",
                        "show",
                        *runtime_args,
                        "--rule",
                        rule_no,
                        "--pack-id",
                        pack_id,
                    ]
                ),
            },
            {
                "name": "ingest_guidelines",
                "command": _shell_join(
                    [
                        "uv",
                        "run",
                        "--project",
                        "review-engine",
                        "python",
                        "-m",
                        "review_engine.cli.ingest_guidelines",
                    ]
                ),
            },
            {
                "name": "targeted_pytest",
                "command": _shell_join(
                    [
                        "uv",
                        "run",
                        "--project",
                        "review-engine",
                        "pytest",
                        "review-engine/tests/test_rule_lifecycle_cli.py",
                        "review-engine/tests/test_rule_runtime.py",
                        "-q",
                    ]
                ),
            },
        ],
    }


def _build_runtime_selector_args(
    *,
    runtime: LoadedRuleContext,
    include_all_packs: bool,
) -> list[str]:
    args = [
        "--language-id",
        runtime.language_id,
        "--profile-id",
        runtime.profile.profile_id,
    ]
    if runtime.context_id:
        args.extend(["--context-id", runtime.context_id])
    if runtime.dialect_id:
        args.extend(["--dialect-id", runtime.dialect_id])
    if include_all_packs:
        args.append("--all-packs")
    return args


def _shell_join(parts: list[str]) -> str:
    return shlex.join(parts)


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


def _iter_inspection_records(
    runtime: LoadedRuleContext,
    *,
    selected_pack_index: dict[str, tuple[RulePackManifest, Path]],
    state_filter: str,
    pack_id: str | None,
) -> list[tuple[RuntimeState, GuidelineRecord]]:
    collected = _iter_runtime_records(
        runtime,
        state_filter=state_filter,
        pack_id=pack_id,
    )
    if state_filter in {"all", "disabled"}:
        collected.extend(
            _iter_disabled_records(
                selected_pack_index=selected_pack_index,
                pack_id=pack_id,
            )
        )
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


def _iter_disabled_records(
    *,
    selected_pack_index: dict[str, tuple[RulePackManifest, Path]],
    pack_id: str | None,
) -> Iterable[tuple[RuntimeState, GuidelineRecord]]:
    for candidate_pack_id, (pack, source_path) in selected_pack_index.items():
        if pack_id and candidate_pack_id != pack_id:
            continue
        for entry in pack.entries:
            if entry.enabled:
                continue
            yield (
                "disabled",
                _build_disabled_record(
                    pack=pack,
                    entry=entry,
                    source_path=source_path,
                ),
            )


def _build_disabled_record(
    *,
    pack: RulePackManifest,
    entry: RuleEntry,
    source_path: Path,
) -> GuidelineRecord:
    base_score = entry.base_score if entry.base_score is not None else 0.6
    severity_default = entry.severity_default if entry.severity_default is not None else base_score
    return GuidelineRecord(
        id=f"{pack.pack_id}:{entry.rule_no}",
        rule_uid=f"{pack.language_id}:{pack.pack_id}:{entry.rule_no}",
        rule_pack=pack.pack_id,
        rule_no=entry.rule_no,
        source=str(source_path),
        pack_id=pack.pack_id,
        source_kind=pack.source_kind,
        language_id=pack.language_id,
        context_id=entry.context_id or pack.context_id,
        dialect_id=entry.dialect_id or pack.dialect_id,
        namespace=pack.namespace,
        section=entry.section,
        title=entry.title,
        text=entry.text,
        summary=entry.summary,
        keywords=entry.keywords,
        tags=entry.tags,
        base_score=base_score,
        priority_tier=entry.priority_tier or pack.default_priority_tier,
        specificity=entry.specificity,
        severity_default=severity_default,
        conflict_action=entry.default_action,
        conflict_reason=entry.rationale,
        active=False,
        reviewability=entry.reviewability,
        applies_to=entry.applies_to,
        category=entry.category,
        false_positive_risk=entry.false_positive_risk,
        trigger_patterns=entry.trigger_patterns,
        bot_comment_template=entry.bot_comment_template,
        fix_guidance=entry.fix_guidance,
        review_rank_default=(
            entry.review_rank_default
            if entry.review_rank_default is not None
            else base_score
        ),
        file_globs=entry.file_globs or pack.file_globs,
        symbol_hints=entry.symbol_hints,
    )


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


def _find_mutation_target(
    *,
    rule_no: str,
    pack_id: str | None,
    selected_pack_index: dict[str, tuple[RulePackManifest, Path]],
) -> tuple[str, Path, bool]:
    matches: list[tuple[str, Path, bool]] = []
    for candidate_pack_id, (pack, source_path) in selected_pack_index.items():
        if pack_id and candidate_pack_id != pack_id:
            continue
        entry_matches = [entry for entry in pack.entries if entry.rule_no == rule_no]
        if len(entry_matches) > 1:
            raise SystemExit(
                "Multiple entries matched "
                f"{rule_no} inside pack {candidate_pack_id}; "
                "canonical pack YAML must keep rule numbers unique."
            )
        if not entry_matches:
            continue
        matches.append((candidate_pack_id, source_path.resolve(), entry_matches[0].enabled))

    if not matches:
        raise SystemExit(f"Rule not found in selected runtime packs: {rule_no}")
    if len(matches) > 1:
        candidate_packs = ", ".join(
            sorted(candidate_pack_id for candidate_pack_id, _path, _enabled in matches)
        )
        raise SystemExit(
            "Multiple rules matched "
            f"{rule_no}; provide --pack-id to disambiguate: {candidate_packs}"
        )
    return matches[0]


def _assert_within_write_boundary(
    source_path: Path,
    *,
    settings: Settings,
    runtime: LoadedRuleContext,
) -> None:
    resolved_source = source_path.resolve()
    allowed_roots = [
        path.resolve()
        for path in [
            settings.public_rule_root or (settings.project_root / "rules"),
            *settings.extension_rule_roots,
        ]
    ]
    runtime_roots = [
        Path(root).resolve()
        for root in [runtime.public_rule_root, *runtime.extension_rule_roots]
        if root
    ]
    for root in allowed_roots + runtime_roots:
        if _is_relative_to(resolved_source, root):
            return
    raise SystemExit(f"Refusing to write outside canonical rule roots: {resolved_source}")


def _set_pack_entry_enabled(
    *,
    path: Path,
    rule_no: str,
    enabled: bool,
) -> bool:
    original_text = path.read_text(encoding="utf-8")
    updated_text = _update_pack_entry_enabled_text(
        original_text,
        rule_no=rule_no,
        enabled=enabled,
    )
    if updated_text == original_text:
        return False
    path.write_text(updated_text, encoding="utf-8")
    return True


def _update_pack_entry_enabled_text(
    text: str,
    *,
    rule_no: str,
    enabled: bool,
) -> str:
    lines = text.splitlines(keepends=True)
    newline = _detect_newline(lines)
    entry_start = _find_entry_start(lines, rule_no=rule_no)
    entry_end = _find_entry_end(lines, entry_start)
    enabled_line = _find_enabled_line(lines, entry_start=entry_start, entry_end=entry_end)

    if enabled:
        if enabled_line is None:
            return text
        if _parse_enabled_value(lines[enabled_line]) is True:
            return text
        del lines[enabled_line]
    else:
        new_line = f"    enabled: false{newline}"
        if enabled_line is None:
            lines.insert(entry_start + 1, new_line)
        elif _parse_enabled_value(lines[enabled_line]) is False:
            return text
        else:
            lines[enabled_line] = new_line
    return "".join(lines)


def _find_entry_start(lines: list[str], *, rule_no: str) -> int:
    for index, line in enumerate(lines):
        if not line.startswith("  - rule_no:"):
            continue
        value = line.split(":", 1)[1].strip().strip("'\"")
        if value == rule_no:
            return index
    raise SystemExit(f"Rule entry not found in canonical pack YAML: {rule_no}")


def _find_entry_end(lines: list[str], entry_start: int) -> int:
    for index in range(entry_start + 1, len(lines)):
        if lines[index].startswith("  - rule_no:"):
            return index
    return len(lines)


def _find_enabled_line(
    lines: list[str],
    *,
    entry_start: int,
    entry_end: int,
) -> int | None:
    for index in range(entry_start + 1, entry_end):
        if lines[index].startswith("    enabled:"):
            return index
    return None


def _parse_enabled_value(line: str) -> bool:
    return line.split(":", 1)[1].strip().strip("'\"").lower() == "true"


def _detect_newline(lines: list[str]) -> str:
    for line in lines:
        if line.endswith("\r\n"):
            return "\r\n"
        if line.endswith("\n"):
            return "\n"
    return "\n"


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)
    payload = args.handler(args)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
