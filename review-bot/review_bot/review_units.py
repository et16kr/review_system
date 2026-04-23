from __future__ import annotations

import re
from dataclasses import dataclass

HUNK_RE = re.compile(r"@@ -(?P<old>\d+)(?:,\d+)? \+(?P<new>\d+)(?:,\d+)? @@")
DEFAULT_MAX_LINES_PER_REVIEW_UNIT = 80


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
    max_lines_per_review_unit: int = DEFAULT_MAX_LINES_PER_REVIEW_UNIT,
) -> list[ReviewUnit]:
    if len(unit.candidate_line_nos) <= max_lines_per_review_unit:
        return [unit]
    if not unit.changed_lines or any(line.marker != "+" for line in unit.changed_lines):
        return [unit]

    added_lines = [line for line in unit.changed_lines if line.new_line_no is not None]
    if len(added_lines) <= max_lines_per_review_unit:
        return [unit]

    split_units: list[ReviewUnit] = []
    for start in range(0, len(added_lines), max_lines_per_review_unit):
        chunk = added_lines[start : start + max_lines_per_review_unit]
        first_line_no = chunk[0].new_line_no
        if first_line_no is None:
            continue
        header = f"@@ -0,0 +{first_line_no},{len(chunk)} @@"
        patch_lines = [header, *[f"+{line.text}" for line in chunk]]
        numbered_lines = [header, *[f"L{line.new_line_no} | + {line.text}" for line in chunk]]
        candidate_line_nos = tuple(
            line.new_line_no for line in chunk if line.new_line_no is not None
        )
        split_units.append(
            ReviewUnit(
                patch="\n".join(patch_lines),
                change_snippet="\n".join(numbered_lines),
                default_line_no=candidate_line_nos[0] if candidate_line_nos else first_line_no,
                candidate_line_nos=candidate_line_nos,
                changed_lines=tuple(chunk),
            )
        )
    return split_units or [unit]
