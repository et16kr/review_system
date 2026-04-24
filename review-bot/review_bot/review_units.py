from __future__ import annotations

import re
from dataclasses import dataclass

HUNK_RE = re.compile(r"@@ -(?P<old>\d+)(?:,\d+)? \+(?P<new>\d+)(?:,\d+)? @@")
DEFAULT_MAX_LINES_PER_REVIEW_UNIT = 80
SAFE_BOUNDARY_MAX_OVERSHOOT = 8


@dataclass(frozen=True)
class ChangedPatchLine:
    marker: str
    text: str
    old_line_no: int | None = None
    new_line_no: int | None = None


@dataclass(frozen=True)
class ReviewUnit:
    patch: str
    change_snippet: str
    default_line_no: int | None
    candidate_line_nos: tuple[int, ...]
    changed_lines: tuple[ChangedPatchLine, ...]


def extract_line_no(patch: str) -> int | None:
    match = HUNK_RE.search(patch)
    if match is None:
        return None
    return int(match.group("new"))


def iter_review_units(
    patch: str,
    *,
    file_path: str | None = None,
    language_id: str | None = None,
    max_lines_per_review_unit: int = DEFAULT_MAX_LINES_PER_REVIEW_UNIT,
) -> list[ReviewUnit]:
    lines = patch.splitlines()
    units: list[ReviewUnit] = []
    current_header: str | None = None
    current_lines: list[str] = []

    for line in lines:
        if line.startswith("@@"):
            if current_header is not None:
                units.append(_build_review_unit(current_header, current_lines))
            current_header = line
            current_lines = []
            continue
        if current_header is not None:
            current_lines.append(line)

    if current_header is not None:
        units.append(_build_review_unit(current_header, current_lines))

    if units:
        expanded: list[ReviewUnit] = []
        for unit in units:
            expanded.extend(
                split_large_added_unit(
                    unit,
                    file_path=file_path,
                    language_id=language_id,
                    max_lines_per_review_unit=max_lines_per_review_unit,
                )
            )
        return expanded
    return [
        ReviewUnit(
            patch=patch,
            change_snippet=patch,
            default_line_no=extract_line_no(patch),
            candidate_line_nos=(),
            changed_lines=(),
        )
    ]


def _build_review_unit(header: str, hunk_lines: list[str]) -> ReviewUnit:
    match = HUNK_RE.match(header)
    old_line_no = int(match.group("old")) if match else None
    new_line_no = int(match.group("new")) if match else None
    changed_lines: list[ChangedPatchLine] = []
    candidate_line_nos: list[int] = []
    numbered_lines: list[str] = [header]

    for raw_line in hunk_lines:
        if raw_line.startswith("\\"):
            continue
        if raw_line.startswith("+") and not raw_line.startswith("+++"):
            changed_lines.append(
                ChangedPatchLine(marker="+", text=raw_line[1:], new_line_no=new_line_no)
            )
            if new_line_no is not None:
                candidate_line_nos.append(new_line_no)
                numbered_lines.append(f"L{new_line_no} | + {raw_line[1:]}")
                new_line_no += 1
            continue
        if raw_line.startswith("-") and not raw_line.startswith("---"):
            changed_lines.append(
                ChangedPatchLine(marker="-", text=raw_line[1:], old_line_no=old_line_no)
            )
            if old_line_no is not None:
                numbered_lines.append(f"OLD{old_line_no} | - {raw_line[1:]}")
                old_line_no += 1
            continue
        if raw_line.startswith(" "):
            if old_line_no is not None:
                old_line_no += 1
            if new_line_no is not None:
                new_line_no += 1

    normalized_candidates = tuple(dict.fromkeys(candidate_line_nos))
    default_line_no = (
        normalized_candidates[0] if normalized_candidates else extract_line_no(header)
    )
    return ReviewUnit(
        patch="\n".join([header, *hunk_lines]),
        change_snippet="\n".join(numbered_lines),
        default_line_no=default_line_no,
        candidate_line_nos=normalized_candidates,
        changed_lines=tuple(changed_lines),
    )


def split_large_added_unit(
    unit: ReviewUnit,
    *,
    file_path: str | None = None,
    language_id: str | None = None,
    max_lines_per_review_unit: int = DEFAULT_MAX_LINES_PER_REVIEW_UNIT,
) -> list[ReviewUnit]:
    if len(unit.candidate_line_nos) <= max_lines_per_review_unit:
        return [unit]
    if not unit.changed_lines or any(line.marker != "+" for line in unit.changed_lines):
        return [unit]

    added_lines = [line for line in unit.changed_lines if line.new_line_no is not None]
    if len(added_lines) <= max_lines_per_review_unit:
        return [unit]

    normalized_language = _normalize_review_language(
        file_path=file_path,
        language_id=language_id,
    )
    if normalized_language == "python":
        python_units = _split_large_boundary_aware_unit(
            added_lines,
            boundary_indexes=_python_safe_boundary_indexes(added_lines),
            max_lines_per_review_unit=max_lines_per_review_unit,
        )
        if python_units is not None:
            return python_units
    if normalized_language == "yaml":
        yaml_units = _split_large_boundary_aware_unit(
            added_lines,
            boundary_indexes=_yaml_safe_boundary_indexes(added_lines),
            max_lines_per_review_unit=max_lines_per_review_unit,
        )
        if yaml_units is not None:
            return yaml_units
    if normalized_language == "tsx":
        tsx_units = _split_large_boundary_aware_unit(
            added_lines,
            boundary_indexes=_tsx_safe_boundary_indexes(added_lines),
            max_lines_per_review_unit=max_lines_per_review_unit,
        )
        if tsx_units is not None:
            return tsx_units

    split_units: list[ReviewUnit] = []
    for start in range(0, len(added_lines), max_lines_per_review_unit):
        chunk = added_lines[start : start + max_lines_per_review_unit]
        built = _build_added_only_review_unit(chunk)
        if built is not None:
            split_units.append(built)
    return split_units or [unit]


def _split_large_boundary_aware_unit(
    added_lines: list[ChangedPatchLine],
    *,
    boundary_indexes: list[int],
    max_lines_per_review_unit: int,
) -> list[ReviewUnit] | None:
    if len(boundary_indexes) <= 1:
        return None

    split_units: list[ReviewUnit] = []
    start_index = 0
    total_lines = len(added_lines)
    while total_lines - start_index > max_lines_per_review_unit:
        split_index = _select_safe_boundary_split_index(
            boundary_indexes=boundary_indexes,
            start_index=start_index,
            total_lines=total_lines,
            max_lines_per_review_unit=max_lines_per_review_unit,
        )
        if split_index is None:
            return None
        built = _build_added_only_review_unit(added_lines[start_index:split_index])
        if built is None:
            return None
        split_units.append(built)
        start_index = split_index

    built = _build_added_only_review_unit(added_lines[start_index:])
    if built is None:
        return None
    split_units.append(built)
    return split_units


def _select_safe_boundary_split_index(
    *,
    boundary_indexes: list[int],
    start_index: int,
    total_lines: int,
    max_lines_per_review_unit: int,
) -> int | None:
    target_index = start_index + max_lines_per_review_unit
    prior_candidates = [
        index for index in boundary_indexes if start_index < index <= target_index
    ]
    if prior_candidates:
        return prior_candidates[-1]

    max_overshoot = min(target_index + SAFE_BOUNDARY_MAX_OVERSHOOT, total_lines - 1)
    next_candidates = [
        index for index in boundary_indexes if target_index < index <= max_overshoot
    ]
    if next_candidates:
        return next_candidates[0]
    return None


def _yaml_safe_boundary_indexes(added_lines: list[ChangedPatchLine]) -> list[int]:
    boundary_indexes: list[int] = [0]
    for index, line in enumerate(added_lines[1:], start=1):
        stripped = line.text.lstrip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- "):
            boundary_indexes.append(index)
            continue
        if stripped.endswith(":"):
            boundary_indexes.append(index)
    return boundary_indexes


def _python_safe_boundary_indexes(added_lines: list[ChangedPatchLine]) -> list[int]:
    boundary_indexes: list[int] = [0]
    previous_indent: int | None = None
    previous_stripped: str | None = None

    for index, line in enumerate(added_lines):
        stripped = line.text.lstrip()
        if not stripped or stripped.startswith("#"):
            continue

        current_indent = len(line.text) - len(stripped)
        if (
            index > 0
            and previous_indent is not None
            and current_indent == previous_indent
            and previous_stripped is not None
            and _python_line_allows_split_after(previous_stripped)
            and _python_line_can_start_split(stripped)
        ):
            boundary_indexes.append(index)

        previous_indent = current_indent
        previous_stripped = stripped

    return boundary_indexes


def _python_line_allows_split_after(stripped: str) -> bool:
    if stripped.endswith(":"):
        return False
    return not stripped.endswith(("\\", "(", "[", "{", ","))


def _python_line_can_start_split(stripped: str) -> bool:
    if stripped.startswith((")", "]", "}", ".", ",")):
        return False
    return not stripped.startswith(
        (
            "if ",
            "elif ",
            "else:",
            "for ",
            "while ",
            "try:",
            "except",
            "finally:",
            "with ",
            "match ",
            "case ",
            "async for ",
            "async with ",
        )
    )


def _tsx_safe_boundary_indexes(added_lines: list[ChangedPatchLine]) -> list[int]:
    boundary_indexes: list[int] = [0]
    previous_tag_indent: int | None = None
    previous_tag_was_closing = False

    for index, line in enumerate(added_lines[1:], start=1):
        stripped = line.text.lstrip()
        if not stripped or not stripped.startswith("<"):
            continue
        current_indent = len(line.text) - len(stripped)
        is_closing_tag = stripped.startswith("</")
        if (
            not is_closing_tag
            and previous_tag_was_closing
            and previous_tag_indent is not None
            and current_indent <= previous_tag_indent
        ):
            boundary_indexes.append(index)
        previous_tag_indent = current_indent
        previous_tag_was_closing = is_closing_tag

    return boundary_indexes


def _normalize_review_language(*, file_path: str | None, language_id: str | None) -> str | None:
    if not file_path:
        return str(language_id).strip().lower() if language_id else None
    lowered_path = file_path.lower()
    if lowered_path.endswith((".py", ".pyi")):
        return "python"
    if lowered_path.endswith((".yaml", ".yml")):
        return "yaml"
    if lowered_path.endswith(".tsx"):
        return "tsx"
    return str(language_id).strip().lower() if language_id else None


def _build_added_only_review_unit(chunk: list[ChangedPatchLine]) -> ReviewUnit | None:
    if not chunk:
        return None
    first_line_no = chunk[0].new_line_no
    if first_line_no is None:
        return None
    header = f"@@ -0,0 +{first_line_no},{len(chunk)} @@"
    patch_lines = [header, *[f"+{line.text}" for line in chunk]]
    numbered_lines = [header, *[f"L{line.new_line_no} | + {line.text}" for line in chunk]]
    candidate_line_nos = tuple(line.new_line_no for line in chunk if line.new_line_no is not None)
    return ReviewUnit(
        patch="\n".join(patch_lines),
        change_snippet="\n".join(numbered_lines),
        default_line_no=candidate_line_nos[0] if candidate_line_nos else first_line_no,
        candidate_line_nos=candidate_line_nos,
        changed_lines=tuple(chunk),
    )
