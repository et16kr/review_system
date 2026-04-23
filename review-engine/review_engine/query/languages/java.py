from __future__ import annotations

from review_engine.query.languages.base import LanguageQueryPlugin, PatternSpec


PLUGIN = LanguageQueryPlugin(
    plugin_id="java",
    display_name="Java",
    default_focus="resource ownership, null handling, thread safety, Spring boundary clarity, and API contract safety",
    pattern_specs=(
        PatternSpec(
            "try_without_resources",
            r"new\s+(?:FileInputStream|FileOutputStream|BufferedReader|BufferedWriter|Socket)\(",
            "Explicit resource construction detected; review whether try-with-resources should own it.",
            1.0,
        ),
        PatternSpec(
            "null_return",
            r"return\s+null\s*;",
            "Null return detected; review API contract clarity and caller burden.",
            0.8,
        ),
        PatternSpec(
            "synchronized_collection",
            r"Collections\.synchronized\w+\(",
            "Synchronized collection wrapper detected; review iteration and thread-safety assumptions.",
            0.74,
        ),
        PatternSpec(
            "string_sql_concatenation",
            r"(?i)(SELECT|UPDATE|DELETE|INSERT).*(\+)",
            "String-based SQL construction detected; review prepared statements and injection risk.",
            0.96,
        ),
        PatternSpec(
            "catch_exception",
            r"catch\s*\(\s*Exception\b",
            "Broad Exception catch detected; review recoverability, cancellation, and error contract clarity.",
            0.84,
        ),
        PatternSpec(
            "new_thread",
            r"new\s+Thread\s*\(",
            "Direct Thread construction detected; review executor ownership, cancellation, and lifecycle control.",
            0.78,
        ),
        PatternSpec(
            "spring_field_injection",
            r"@Autowired\s+(?:private|protected|public)\s+(?!final\b)[\w<>\[\], ?]+\s+\w+\s*;",
            "Spring field injection detected; review whether constructor injection would make dependencies and tests clearer.",
            0.92,
        ),
        PatternSpec(
            "spring_transaction_on_controller",
            r"(?is)(@(?:RestController|Controller)\b[\s\S]{0,500}@Transactional)|(@Transactional\b[\s\S]{0,500}@(?:RestController|Controller)\b)",
            "Transactional boundary appears in a controller class; review whether HTTP and transaction ownership are being mixed.",
            0.9,
        ),
        PatternSpec(
            "spring_configuration_properties",
            r"@ConfigurationProperties\b",
            "ConfigurationProperties binding detected; review validation and configuration-boundary safety.",
            0.78,
        ),
        PatternSpec(
            "spring_findall_request_path",
            r"(?is)@(?:RestController|Controller)\b[\s\S]{0,500}\.findAll\s*\(",
            "findAll() detected in a Spring request path; review data volume, DTO shaping, and accidental N+1 surfaces.",
            0.74,
        ),
    ),
    hinted_rules={
        "try_without_resources": ("JAVA.1", "JAVA.4"),
        "null_return": ("JAVA.2", "JAVA.3"),
        "synchronized_collection": ("JAVA.PROJ.2", "JAVA.PROJ.4"),
        "string_sql_concatenation": ("JAVA.PROJ.1", "JAVA.PROJ.3"),
        "catch_exception": ("JAVA.PROJ.5",),
        "new_thread": ("JAVA.PROJ.6",),
        "spring_field_injection": ("JAVA.SPRING.1",),
        "spring_transaction_on_controller": ("JAVA.SPRING.2",),
        "spring_configuration_properties": ("JAVA.SPRING.3",),
        "spring_findall_request_path": ("JAVA.SPRING.4", "JAVA.SPRING.REF.1"),
    },
    direct_hint_patterns={
        "try_without_resources",
        "null_return",
        "synchronized_collection",
        "string_sql_concatenation",
        "catch_exception",
        "new_thread",
        "spring_field_injection",
        "spring_transaction_on_controller",
        "spring_configuration_properties",
        "spring_findall_request_path",
    },
)
