from __future__ import annotations

from pathlib import Path

from review_engine.query.repository_scan import render_repo_scan_markdown, scan_repository


def test_repository_scan_finds_code_patterns(tmp_path: Path) -> None:
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "sample.cpp").write_text(
        "#include <stdio.h>\nvoid bad(){ int* ptr = new int(1); free(ptr); // comment\n"
        "for (int i = 0; i < 3; ++i) { continue; } }\n",
        encoding="utf-8",
    )

    report = scan_repository(tmp_path, include_dirs=["src"])

    assert report.scanned_files == 1
    assert report.matched_files == 1
    assert "raw_new" in report.aggregate_patterns
    assert "continue_usage" in report.aggregate_patterns


def test_repository_scan_excludes_thirdparty_by_default(tmp_path: Path) -> None:
    thirdparty_dir = tmp_path / "thirdparty"
    thirdparty_dir.mkdir()
    (thirdparty_dir / "vendor.c").write_text(
        "#include <stdio.h>\nvoid noisy(){ printf(\"x\"); }\n",
        encoding="utf-8",
    )

    report = scan_repository(tmp_path)

    assert report.scanned_files == 0
    assert report.matched_files == 0
    assert render_repo_scan_markdown(report).startswith("# Repository Scan Report")


def test_repository_scan_supports_ignore_patterns_and_fragments(tmp_path: Path) -> None:
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "keep.cpp").write_text(
        "#include <stdio.h>\nvoid bad(){ int* ptr = new int(1); free(ptr); }\n",
        encoding="utf-8",
    )
    (src_dir / "vendor_generated.cpp").write_text(
        "#include <stdio.h>\nvoid noisy(){ printf(\"x\"); }\n",
        encoding="utf-8",
    )

    report = scan_repository(
        tmp_path,
        include_dirs=["src"],
        exclude_fragments=["vendor_generated"],
        ignore_patterns=["ownership_ambiguity"],
    )

    assert report.scanned_files == 1
    assert report.matched_files == 1
    assert "ownership_ambiguity" not in report.aggregate_patterns
