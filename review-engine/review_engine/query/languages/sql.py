from __future__ import annotations

from review_engine.query.languages.base import LanguageQueryPlugin, PatternSpec


PLUGIN = LanguageQueryPlugin(
    plugin_id="sql",
    display_name="SQL",
    default_focus="result correctness, explicit joins, destructive statements, and dialect-safe query patterns",
    pattern_specs=(
        PatternSpec(
            "select_star",
            r"(?i)\bselect\s+\*",
            "SELECT * detected; review column contract stability and unnecessary payload.",
            0.88,
        ),
        PatternSpec(
            "implicit_join",
            r"(?i)\bfrom\s+\w+\s*,\s*\w+",
            "Implicit join syntax detected; review join intent and accidental cartesian products.",
            0.92,
        ),
        PatternSpec(
            "delete_without_where",
            r"(?i)\b(?:delete\s+from|update\s+\w+\s+set)\b(?![^;]*\bwhere\b)",
            "Potential destructive statement without WHERE detected; review safety guardrails.",
            1.0,
        ),
        PatternSpec(
            "dynamic_sql",
            r"(?is)(execute|format\(|concat\().*(select|update|delete|insert)",
            "Dynamic SQL construction detected; review parameterization and injection risk.",
            0.95,
        ),
        PatternSpec(
            "order_by_ordinal",
            r"(?i)\border\s+by\s+\d+\b",
            "Ordinal ORDER BY detected; review readability and schema-coupling of sort behavior.",
            0.78,
        ),
        PatternSpec(
            "not_in_subquery",
            r"(?i)\bnot\s+in\s*\(\s*select\b",
            "NOT IN subquery detected; review NULL semantics and whether NOT EXISTS is safer for the intended result set.",
            0.82,
        ),
    ),
    hinted_rules={
        "select_star": ("SQL.1", "SQL.4"),
        "implicit_join": ("SQL.2", "SQL.3"),
        "delete_without_where": ("SQL.PROJ.1", "SQL.PROJ.2"),
        "dynamic_sql": ("SQL.PG.1", "SQL.PG.2", "SQL.PG.3", "SQL.PROJ.3"),
        "order_by_ordinal": ("SQL.5",),
        "not_in_subquery": ("SQL.6",),
    },
    direct_hint_patterns={
        "select_star",
        "implicit_join",
        "delete_without_where",
        "dynamic_sql",
        "order_by_ordinal",
        "not_in_subquery",
    },
)
