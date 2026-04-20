from __future__ import annotations

from pathlib import Path

from review_engine.parser.guidelines_parser import parse_cpp_core_guidelines
from review_engine.parser.internal_convention_parser import parse_internal_convention


def test_parse_internal_convention_handles_wrapped_titles(fixture_root: Path) -> None:
    markdown = (fixture_root / "altibase_sample.md").read_text(encoding="utf-8")
    records = parse_internal_convention(markdown, source="fixture")

    rule_map = {record.rule_no: record for record in records}
    assert "ALTI-MEM-006" in rule_map
    assert (
        rule_map["ALTI-MEM-006"].title
        == "Allocate and free memory in the same module and at the same abstraction level"
    )
    assert rule_map["ALTI-COM-001"].section == "ALTI-COM"
    assert rule_map["Rule-R1"].summary == "Functions that can fail return `IDE_RC`"


def test_parse_cpp_core_guidelines_extracts_rules(fixture_root: Path) -> None:
    html = (fixture_root / "cpp_core_sample.html").read_text(encoding="utf-8")
    records = parse_cpp_core_guidelines(html, source="fixture")

    rule_map = {record.rule_no: record for record in records}
    assert set(rule_map) == {"R.10", "R.11", "CP.20"}
    assert rule_map["R.10"].section == "R"
    assert "malloc" in rule_map["R.10"].summary.lower()
    assert "lock" in rule_map["CP.20"].text.lower()
