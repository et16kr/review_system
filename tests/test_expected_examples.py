from __future__ import annotations

import json
from pathlib import Path


def test_expected_examples_are_present_in_results(real_search_service) -> None:
    spec_path = Path("examples/expected_retrieval_examples.json")
    spec = json.loads(spec_path.read_text(encoding="utf-8"))

    for case in spec:
        input_path = Path(case["input"])
        assert not input_path.is_absolute(), f"{spec_path} must use repo-local inputs: {input_path}"
        assert input_path.exists(), f"Missing expected example input: {input_path}"
        payload = input_path.read_text(encoding="utf-8")
        if input_path.suffix == ".diff":
            response = real_search_service.review_diff(payload, top_k=12)
        else:
            response = real_search_service.review_code(payload, top_k=12)

        returned_rules = {result.rule_no for result in response.results}
        for expected_rule in case["expected_rules"]:
            assert expected_rule in returned_rules, (
                f"{input_path} missing expected rule {expected_rule}"
            )
