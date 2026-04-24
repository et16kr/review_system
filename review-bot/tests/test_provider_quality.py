from __future__ import annotations

import json

from review_bot.cli.compare_provider_quality import main as compare_provider_quality_main
from review_bot.cli.evaluate_provider_quality import main as provider_quality_main
from review_bot.providers.stub_provider import StubReviewCommentProvider
from review_bot.quality.provider_quality import (
    build_provider_quality_comparison,
    evaluate_provider_quality,
    load_provider_quality_cases,
    render_markdown_report,
    render_provider_comparison_markdown,
)


def test_stub_provider_quality_gate_passes_for_golden_corpus() -> None:
    cases = load_provider_quality_cases()

    report = evaluate_provider_quality(
        provider=StubReviewCommentProvider(),
        cases=cases,
        provider_name="stub",
    )

    assert report["status"] == "passed"
    assert report["summary"]["failed_cases"] == 0
    assert {result["case_id"] for result in report["results"]} >= {
        "cuda_async_default_stream",
        "cuda_cooperative_groups_grid_sync",
    }


def test_provider_quality_markdown_report_includes_cuda_regression() -> None:
    report = evaluate_provider_quality(
        provider=StubReviewCommentProvider(),
        cases=load_provider_quality_cases(),
        provider_name="stub",
    )

    markdown = render_markdown_report(report)

    assert "# Review Bot Provider Quality" in markdown
    assert "| cuda_async_default_stream | passed |" in markdown
    assert "| cuda_cooperative_groups_grid_sync | passed |" in markdown


def test_openai_provider_quality_cli_skips_without_api_key(monkeypatch, capsys, tmp_path) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("BOT_OPENAI_MODEL", "local-model")
    monkeypatch.setenv("BOT_OPENAI_BASE_URL", "http://127.0.0.1:11434/v1")
    json_output = tmp_path / "openai.json"

    exit_code = provider_quality_main(
        ["--provider", "openai", "--json-output", str(json_output)]
    )

    assert exit_code == 0
    rendered = capsys.readouterr().out
    assert "status: `skipped`" in rendered
    assert "transport_class=non_default_openai_compatible_base_url" in rendered
    report = json.loads(json_output.read_text(encoding="utf-8"))
    assert report["provider_runtime"] == {
        "configured_provider": "openai",
        "effective_provider": "openai",
        "fallback_used": False,
        "configured_model": "local-model",
        "endpoint_base_url": "http://127.0.0.1:11434/v1",
        "transport_class": "non_default_openai_compatible_base_url",
    }


def test_provider_quality_comparison_handles_openai_skipped() -> None:
    stub_report = evaluate_provider_quality(
        provider=StubReviewCommentProvider(),
        cases=load_provider_quality_cases(),
        provider_name="stub",
        provider_runtime={
            "configured_provider": "stub",
            "effective_provider": "stub",
            "fallback_used": False,
            "transport_class": "deterministic_stub",
        },
    )
    openai_report = {
        "provider": "openai",
        "status": "skipped",
        "skip_reason": "OPENAI_API_KEY is not set",
        "provider_runtime": {
            "configured_provider": "openai",
            "effective_provider": "openai",
            "fallback_used": False,
            "configured_model": "local-model",
            "endpoint_base_url": "http://127.0.0.1:11434/v1",
            "transport_class": "non_default_openai_compatible_base_url",
        },
        "summary": {"total_cases": 0, "passed_cases": 0, "failed_cases": 0},
        "results": [],
    }

    comparison = build_provider_quality_comparison(
        stub_report=stub_report,
        openai_report=openai_report,
        generated_at="2026-04-23T00:00:00Z",
        corpus_revision="test-corpus",
    )
    markdown = render_provider_comparison_markdown(comparison)

    assert comparison["openai_status"] == "skipped"
    assert comparison["stub_provider_runtime"]["transport_class"] == "deterministic_stub"
    assert (
        comparison["openai_provider_runtime"]["transport_class"]
        == "non_default_openai_compatible_base_url"
    )
    assert comparison["human_review_required"] is False
    assert comparison["recommended_next_action"] == (
        "defer_openai_comparison_until_api_key_available"
    )
    assert "stub_provider_runtime" in markdown
    assert "openai_provider_runtime" in markdown
    assert "Capture again with `OPENAI_API_KEY`" in markdown


def test_provider_quality_comparison_flags_human_review_deltas() -> None:
    stub_report = evaluate_provider_quality(
        provider=StubReviewCommentProvider(),
        cases=load_provider_quality_cases(),
        provider_name="stub",
    )
    openai_report = json.loads(json.dumps(stub_report))
    openai_report["provider"] = "openai"
    first_result = openai_report["results"][0]
    first_result["metrics"]["line_no_in_candidates"] = False
    first_result["missing_terms"] = ["검증"]
    first_result["metrics"]["missing_terms"] = ["검증"]
    first_result["draft"]["title"] = first_result["draft"]["title"] + " - extra context"
    first_result["metrics"]["title_length"] = len(first_result["draft"]["title"])

    comparison = build_provider_quality_comparison(
        stub_report=stub_report,
        openai_report=openai_report,
        generated_at="2026-04-23T00:00:00Z",
        corpus_revision="test-corpus",
    )

    assert comparison["human_review_required"] is True
    delta = next(
        item
        for item in comparison["case_deltas"]
        if item["case_id"] == first_result["case_id"]
    )
    assert delta["review_recommendation"] == "human_review"
    assert "line anchoring mismatch" in delta["review_signals"]
    assert "required term coverage regression" in delta["review_signals"]


def test_provider_quality_comparison_flags_missing_comparable_case() -> None:
    stub_report = evaluate_provider_quality(
        provider=StubReviewCommentProvider(),
        cases=load_provider_quality_cases(),
        provider_name="stub",
    )
    openai_report = json.loads(json.dumps(stub_report))
    openai_report["provider"] = "openai"
    openai_report["results"] = openai_report["results"][1:]

    comparison = build_provider_quality_comparison(
        stub_report=stub_report,
        openai_report=openai_report,
        generated_at="2026-04-23T00:00:00Z",
        corpus_revision="test-corpus",
    )

    assert comparison["human_review_required"] is True
    delta = next(
        item
        for item in comparison["case_deltas"]
        if item["openai_status"] == "missing"
    )
    assert delta["review_recommendation"] == "defer"
    assert delta["human_review_required"] is True
    assert "missing comparable provider result" in delta["review_signals"]


def test_provider_quality_comparison_cli_writes_artifacts(tmp_path) -> None:
    stub_report = evaluate_provider_quality(
        provider=StubReviewCommentProvider(),
        cases=load_provider_quality_cases(),
        provider_name="stub",
        provider_runtime={
            "configured_provider": "stub",
            "effective_provider": "stub",
            "fallback_used": False,
            "transport_class": "deterministic_stub",
        },
    )
    openai_report = {
        "provider": "openai",
        "status": "skipped",
        "skip_reason": "OPENAI_API_KEY is not set",
        "provider_runtime": {
            "configured_provider": "openai",
            "effective_provider": "openai",
            "fallback_used": False,
            "configured_model": "gpt-local",
            "endpoint_base_url": "http://127.0.0.1:11434/v1",
            "transport_class": "non_default_openai_compatible_base_url",
        },
        "summary": {"total_cases": 0, "passed_cases": 0, "failed_cases": 0},
        "results": [],
    }
    stub_path = tmp_path / "stub.json"
    openai_path = tmp_path / "openai.json"
    output_path = tmp_path / "comparison.md"
    json_output_path = tmp_path / "comparison.json"
    stub_path.write_text(json.dumps(stub_report), encoding="utf-8")
    openai_path.write_text(json.dumps(openai_report), encoding="utf-8")

    exit_code = compare_provider_quality_main(
        [
            "--stub-json",
            str(stub_path),
            "--openai-json",
            str(openai_path),
            "--generated-at",
            "2026-04-23T00:00:00Z",
            "--output",
            str(output_path),
            "--json-output",
            str(json_output_path),
        ]
    )

    assert exit_code == 0
    markdown = output_path.read_text(encoding="utf-8")
    comparison = json.loads(json_output_path.read_text(encoding="utf-8"))
    assert "# Review Bot Provider Comparison" in markdown
    assert "endpoint_base_url=http://127.0.0.1:11434/v1" in markdown
    assert comparison["openai_status"] == "skipped"
    assert (
        comparison["openai_provider_runtime"]["transport_class"]
        == "non_default_openai_compatible_base_url"
    )
