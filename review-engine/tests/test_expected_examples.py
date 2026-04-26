from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _repo_path(relative_path: str) -> Path:
    return PROJECT_ROOT / relative_path


def test_expected_examples_are_present_in_results(real_search_service) -> None:
    spec_path = _repo_path("examples/expected_retrieval_examples.json")
    spec = json.loads(spec_path.read_text(encoding="utf-8"))

    for case in spec:
        input_path = _repo_path(str(case["input"]))
        assert not Path(str(case["input"])).is_absolute(), (
            f"{spec_path} must use repo-local inputs: {input_path}"
        )
        assert input_path.exists(), f"Missing expected example input: {input_path}"
        review_path = case.get("review_path")
        if review_path:
            review_path_value = Path(str(review_path))
            assert not review_path_value.is_absolute(), (
                f"{spec_path} must use repo-local review_path hints: {review_path}"
            )
            assert ".." not in review_path_value.parts, (
                f"{spec_path} review_path must not escape repo root: {review_path}"
            )
        payload = input_path.read_text(encoding="utf-8")
        if input_path.suffix == ".diff":
            kwargs = {"file_path": review_path} if review_path else {}
            response = real_search_service.review_diff(payload, top_k=12, **kwargs)
        else:
            response = real_search_service.review_code(
                payload,
                top_k=12,
                file_path=review_path or str(case["input"]),
            )

        returned_rules = {result.rule_no for result in response.results}
        for expected_rule in case["expected_rules"]:
            assert expected_rule in returned_rules, (
                f"{input_path} missing expected rule {expected_rule}"
            )


def test_expected_examples_do_not_reference_removed_altibase_corpus() -> None:
    spec_path = _repo_path("examples/expected_retrieval_examples.json")
    spec = json.loads(spec_path.read_text(encoding="utf-8"))

    for case in spec:
        input_path = str(case["input"]).lower()
        assert "altidev4" not in input_path
        assert "altibase" not in input_path
