from __future__ import annotations

from app.models import QueryAnalysis
from app.query.cpp_feature_extractor import extract_query_patterns


def build_query_analysis(source_text: str, input_kind: str) -> QueryAnalysis:
    patterns = extract_query_patterns(source_text)
    if patterns:
        concerns = " ".join(pattern.description for pattern in patterns)
        query_text = (
            f"Review this C++ {input_kind} for the following likely issues. {concerns}"
        )
    else:
        query_text = (
            f"Review this C++ {input_kind} for memory lifetime issues, portability concerns, "
            "error handling issues, naming or formatting violations, and compatible guideline "
            "recommendations."
        )

    return QueryAnalysis(input_kind=input_kind, query_text=query_text, patterns=patterns)
