from __future__ import annotations

from review_engine.query.languages.base import LanguageQueryPlugin, PatternSpec


PLUGIN = LanguageQueryPlugin(
    plugin_id="sql",
    display_name="SQL",
    default_focus="result correctness, explicit joins, destructive statements, dbt model clarity, and migration safety",
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
        PatternSpec(
            "group_by_ordinal",
            r"(?i)\bgroup\s+by\s+\d+(?:\s*,\s*\d+)*\b",
            "Ordinal GROUP BY detected; review long-lived grouping clarity in analytics or reporting SQL.",
            0.84,
        ),
        PatternSpec(
            "limit_without_order",
            r"(?is)\bselect\b(?!.*\border\s+by\b).*?\blimit\s+\d+\b",
            "LIMIT without ORDER BY detected; review whether the query result is meant to be stable or reproducible.",
            0.86,
        ),
        PatternSpec(
            "union_distinct",
            r"(?i)\bunion\b(?!\s+all\b)",
            "UNION without ALL detected; review whether deduplication semantics are intentional in the warehouse or report contract.",
            0.72,
        ),
        PatternSpec(
            "dbt_select_star_ref",
            r"(?is)\bselect\s+\*\s+from\s+\{\{\s*(?:ref|source)\s*\(",
            "dbt model selects * from ref/source; review projection contract drift across model boundaries.",
            0.88,
        ),
        PatternSpec(
            "dbt_run_query",
            r"(?is)\brun_query\s*\(",
            "dbt run_query detected; review dynamic SQL structure and warehouse-side effects.",
            0.9,
        ),
        PatternSpec(
            "dbt_run_query_side_effect_without_command_scope",
            (
                r"(?is)\A(?!.*\bflags\.WHICH\b).*?\brun_query\s*\(\s*['\"]\s*"
                r"(?:delete|insert|update|merge|drop|alter|create|truncate|vacuum)\b"
            ),
            (
                "Side-effecting dbt run_query call lacks an explicit flags.WHICH command scope; "
                "review compile/docs execution paths."
            ),
            0.96,
        ),
        PatternSpec(
            "migration_drop_table",
            r"(?i)\bdrop\s+table\b",
            "DROP TABLE detected; review staged rollout and compatibility impact.",
            0.98,
        ),
        PatternSpec(
            "migration_drop_cascade",
            r"(?is)\bdrop\s+(?:table|column)\b[\s\S]{0,120}\bcascade\b",
            "DROP ... CASCADE detected; review fan-out destructive impact and whether dependent objects are being removed too broadly.",
            0.99,
        ),
        PatternSpec(
            "migration_drop_column",
            r"(?is)\balter\s+table\b[\s\S]{0,200}\bdrop\s+column\b",
            "DROP COLUMN detected; review compatibility windows and reader safety during rollout.",
            0.96,
        ),
        PatternSpec(
            "migration_set_not_null",
            r"(?is)\balter\s+table\b[\s\S]{0,200}\bset\s+not\s+null\b",
            "SET NOT NULL detected; review backfill and validation sequencing before tightening the constraint.",
            0.92,
        ),
        PatternSpec(
            "migration_create_index_plain",
            r"(?i)\bcreate\s+index\b(?!\s+concurrently\b)",
            "CREATE INDEX without CONCURRENTLY detected; review lock impact in PostgreSQL migration paths.",
            0.86,
        ),
    ),
    hinted_rules={
        "select_star": ("SQL.1", "SQL.4"),
        "implicit_join": ("SQL.2", "SQL.3"),
        "delete_without_where": ("SQL.PROJ.1", "SQL.PROJ.2"),
        "dynamic_sql": ("SQL.PG.1", "SQL.PG.2", "SQL.PG.3", "SQL.PROJ.3"),
        "order_by_ordinal": ("SQL.5",),
        "not_in_subquery": ("SQL.6",),
        "group_by_ordinal": ("SQL.WH.1",),
        "limit_without_order": ("SQL.WH.2",),
        "union_distinct": ("SQL.WH.REF.1",),
        "dbt_select_star_ref": ("SQL.DBT.1",),
        "dbt_run_query": ("SQL.DBT.2",),
        "dbt_run_query_side_effect_without_command_scope": ("SQL.DBT.3",),
        "migration_drop_table": ("SQL.MIG.1",),
        "migration_drop_cascade": ("SQL.MIG.5", "SQL.MIG.1", "SQL.MIG.2"),
        "migration_drop_column": ("SQL.MIG.2",),
        "migration_set_not_null": ("SQL.MIG.3",),
        "migration_create_index_plain": ("SQL.MIG.4",),
    },
    direct_hint_patterns={
        "select_star",
        "implicit_join",
        "delete_without_where",
        "dynamic_sql",
        "order_by_ordinal",
        "not_in_subquery",
        "group_by_ordinal",
        "limit_without_order",
        "union_distinct",
        "dbt_select_star_ref",
        "dbt_run_query",
        "dbt_run_query_side_effect_without_command_scope",
        "migration_drop_table",
        "migration_drop_cascade",
        "migration_drop_column",
        "migration_set_not_null",
        "migration_create_index_plain",
    },
)
