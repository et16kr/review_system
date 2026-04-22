from __future__ import annotations

from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RULE_SOURCES_ROOT = PROJECT_ROOT / "rule_sources"
RULES_ROOT = PROJECT_ROOT / "rules"

SECTION_TITLES = {
    "candidate_canonical_rule_groups": "Candidate Canonical Rule Groups",
    "reference_only_guidance": "Reference-Only Guidance",
}
ALLOWED_STATUSES = {"mapped", "reference_only", "excluded"}


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _strip_front_matter(markdown: str) -> str:
    if not markdown.startswith("---\n"):
        return markdown
    _head, _front_matter, body = markdown.split("---\n", 2)
    return body


def _extract_section_bullet_counts(path: Path) -> dict[str, int]:
    body = _strip_front_matter(path.read_text(encoding="utf-8"))
    current_section: str | None = None
    counts = {section_id: 0 for section_id in SECTION_TITLES}

    for raw_line in body.splitlines():
        line = raw_line.rstrip()
        if line.startswith("## "):
            heading = line[3:].strip()
            current_section = next(
                (section_id for section_id, title in SECTION_TITLES.items() if title == heading),
                None,
            )
            continue
        if current_section and line.lstrip().startswith("- "):
            counts[current_section] += 1
    return counts


def _rule_index() -> set[str]:
    rule_nos: set[str] = set()
    for pack_path in RULES_ROOT.glob("*/*/*.yaml"):
        if "/packs/" not in str(pack_path):
            continue
        payload = _load_yaml(pack_path)
        for entry in payload.get("entries", []):
            rule_nos.add(entry["rule_no"])
    return rule_nos


def test_source_coverage_matrix_is_atomized_and_complete() -> None:
    manifest = _load_yaml(RULE_SOURCES_ROOT / "manifest.yaml")
    coverage = _load_yaml(RULE_SOURCES_ROOT / "coverage_matrix.yaml")
    all_rule_nos = _rule_index()

    assert coverage["coverage_granularity"] == "source_atom"
    assert set(coverage["covered_sections"]) == set(SECTION_TITLES)

    source_paths = {
        source["rule_source_id"]: RULE_SOURCES_ROOT / source["path"]
        for language in manifest["languages"]
        for source in language["sources"]
    }

    coverage_sources = {
        source["rule_source_id"]: source
        for language in coverage["languages"]
        for source in language["sources"]
    }

    assert set(coverage_sources) == set(source_paths)

    for rule_source_id, source_path in source_paths.items():
        coverage_source = coverage_sources[rule_source_id]
        expected_counts = _extract_section_bullet_counts(source_path)

        assert coverage_source["section_counts"] == expected_counts
        assert len(coverage_source["atoms"]) == sum(expected_counts.values())

        seen_atom_ids: set[str] = set()
        actual_counts = {section_id: 0 for section_id in SECTION_TITLES}
        for atom in coverage_source["atoms"]:
            atom_id = atom["source_atom_id"]
            section_id = atom["section_id"]
            status = atom["status"]

            assert atom_id not in seen_atom_ids
            seen_atom_ids.add(atom_id)

            assert section_id in SECTION_TITLES
            actual_counts[section_id] += 1

            assert status in ALLOWED_STATUSES
            assert status != "pending"
            assert atom["pack_targets"]
            assert atom["reviewability_mix"]

            canonical_rules = atom.get("canonical_rules", [])
            if status == "excluded":
                assert not canonical_rules
                continue

            assert canonical_rules
            assert set(canonical_rules) <= all_rule_nos

        assert actual_counts == expected_counts
