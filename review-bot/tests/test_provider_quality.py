from __future__ import annotations

from review_bot.cli.evaluate_provider_quality import main as provider_quality_main
from review_bot.providers.stub_provider import StubReviewCommentProvider
from review_bot.quality.provider_quality import (
    evaluate_provider_quality,
    load_provider_quality_cases,
    render_markdown_report,
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


def test_openai_provider_quality_cli_skips_without_api_key(monkeypatch, capsys) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    exit_code = provider_quality_main(["--provider", "openai"])

    assert exit_code == 0
    assert "status: `skipped`" in capsys.readouterr().out
