from __future__ import annotations

import os
from collections import Counter
from pathlib import Path

from review_engine.models import RepoFileFinding, RepoScanReport
from review_engine.query.cpp_feature_extractor import extract_query_patterns

CODE_SUFFIXES = {".c", ".cc", ".cpp", ".cxx", ".h", ".hpp"}
DEFAULT_EXCLUDED_DIRS = {
    ".git",
    ".venv",
    ".ruff_cache",
    "altibase_home",
    "build",
    "build-compat",
    "out",
    "target",
    "thirdparty",
}


def scan_repository(
    root: Path,
    *,
    include_dirs: list[str] | None = None,
    exclude_dirs: list[str] | None = None,
    exclude_fragments: list[str] | None = None,
    ignore_patterns: list[str] | None = None,
) -> RepoScanReport:
    root = root.expanduser().resolve()
    include_set = {item for item in (include_dirs or []) if item}
    exclude_set = set(DEFAULT_EXCLUDED_DIRS)
    exclude_set.update(item for item in (exclude_dirs or []) if item)
    exclude_fragment_set = {item for item in (exclude_fragments or []) if item}
    ignore_pattern_set = {item for item in (ignore_patterns or []) if item}

    aggregate_patterns: Counter[str] = Counter()
    findings: list[RepoFileFinding] = []
    scanned_files = 0

    for file_path in _iter_source_files(root, include_set, exclude_set, exclude_fragment_set):
        scanned_files += 1
        content = _read_text(file_path)
        patterns = [
            pattern
            for pattern in extract_query_patterns(content)
            if pattern.name not in ignore_pattern_set
        ]
        if not patterns:
            continue

        for pattern in patterns:
            aggregate_patterns[pattern.name] += 1

        findings.append(
            RepoFileFinding(
                path=str(file_path),
                score=round(sum(pattern.weight for pattern in patterns), 4),
                pattern_count=len(patterns),
                patterns=patterns,
            )
        )

    findings.sort(
        key=lambda finding: (
            finding.score,
            finding.pattern_count,
            -len(finding.path),
        ),
        reverse=True,
    )
    return RepoScanReport(
        root=str(root),
        scanned_files=scanned_files,
        matched_files=len(findings),
        aggregate_patterns=dict(aggregate_patterns.most_common()),
        findings=findings,
    )


def render_repo_scan_markdown(report: RepoScanReport, top_files: int = 30) -> str:
    lines = [
        "# Repository Scan Report",
        "",
        f"- Root: `{report.root}`",
        f"- Scanned files: {report.scanned_files}",
        f"- Matched files: {report.matched_files}",
        "",
        "## Top Patterns",
        "",
    ]

    for name, count in list(report.aggregate_patterns.items())[:15]:
        lines.append(f"- `{name}`: {count}")

    lines.extend(["", "## Top Files", ""])
    for finding in report.findings[:top_files]:
        pattern_names = ", ".join(pattern.name for pattern in finding.patterns[:6])
        lines.append(
            f"- `{finding.path}` | score={finding.score:.2f} | "
            f"patterns={finding.pattern_count} | {pattern_names}"
        )
    lines.append("")
    return "\n".join(lines)


def _iter_source_files(
    root: Path,
    include_dirs: set[str],
    exclude_dirs: set[str],
    exclude_fragments: set[str],
):
    for current_root, dir_names, file_names in os.walk(root):
        current_path = Path(current_root)
        relative_parts = current_path.relative_to(root).parts
        if include_dirs and relative_parts and relative_parts[0] not in include_dirs:
            dir_names[:] = []
            continue
        if include_dirs and not relative_parts:
            file_names[:] = []

        dir_names[:] = [
            dir_name
            for dir_name in dir_names
            if dir_name not in exclude_dirs and not dir_name.startswith(".")
        ]

        for file_name in file_names:
            file_path = current_path / file_name
            if file_path.suffix.lower() not in CODE_SUFFIXES:
                continue
            file_path_text = str(file_path)
            if exclude_fragments and any(
                fragment in file_path_text for fragment in exclude_fragments
            ):
                continue
            if file_path.suffix.lower() in CODE_SUFFIXES:
                yield file_path


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")
