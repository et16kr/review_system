from __future__ import annotations

from pathlib import Path

from review_engine.parser.guidelines_parser import parse_cpp_core_guidelines


def test_parse_cpp_core_guidelines_extracts_rules(fixture_root: Path) -> None:
    html = (fixture_root / "cpp_core_sample.html").read_text(encoding="utf-8")
    records = parse_cpp_core_guidelines(html, source="fixture")

    rule_map = {record.rule_no: record for record in records}
    assert set(rule_map) == {"R.10", "R.11", "CP.20"}
    assert rule_map["R.10"].section == "R"
    assert "malloc" in rule_map["R.10"].summary.lower()
    assert "lock" in rule_map["CP.20"].text.lower()
