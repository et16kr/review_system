from __future__ import annotations

from app.query.code_to_query import build_query_analysis


def test_query_analysis_detects_internal_and_cpp_patterns() -> None:
    code = """
    #include <stdio.h>
    void bad() {
        int* ptr = new int(1);
        free(ptr);
        // wrong comment style
        for (int i = 0; i < 10; ++i) { continue; }
    }
    """

    analysis = build_query_analysis(code, input_kind="code")
    names = {pattern.name for pattern in analysis.patterns}

    assert {"raw_new", "malloc_free", "line_comment", "continue_usage"} <= names
    assert "likely issues" in analysis.query_text
