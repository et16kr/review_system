from __future__ import annotations

from review_engine.ingest.build_records import build_guideline_records
from review_engine.ingest.conflict_resolver import resolve_conflicts
from review_engine.models import ParsedRule


def test_conflict_resolution_excludes_disabled_cpp_rule(fixture_settings) -> None:
    parsed_rules = [
        ParsedRule(
            rule_no="ALTI-COM-001",
            source="fixture",
            source_family="altibase",
            section="ALTI-COM",
            title="Use only block comments",
            text="Only block comments are allowed.",
            summary="Use only block comments",
            keywords=["comments", "block"],
        ),
        ParsedRule(
            rule_no="NL.16",
            source="fixture",
            source_family="cpp_core",
            section="NL",
            title="Use a conventional class member declaration order",
            text="External style rule.",
            summary="External style rule",
            keywords=["style", "layout"],
        ),
    ]

    records = build_guideline_records(parsed_rules, fixture_settings)
    resolution = resolve_conflicts(records, fixture_settings)
    cpp_record = next(record for record in resolution.all_records if record.rule_no == "NL.16")

    assert cpp_record.active is False
    assert cpp_record.conflict_policy == "excluded"
    assert any(record.rule_no == "ALTI-COM-001" for record in resolution.active_records)
