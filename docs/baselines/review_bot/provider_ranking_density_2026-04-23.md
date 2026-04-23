# Provider Ranking Density Baseline - 2026-04-23

## Scope

- Source baseline: working tree on top of commit `45ed077`.
- Provider gate: packaged corpus in `review-bot/review_bot/quality/provider_quality_cases.json`.
- Density gate: local GitLab smoke fixture contracts in `ops/fixtures/review_smoke/*/expected_smoke.json`.
- OpenAI comparison: opt-in only; skipped without `OPENAI_API_KEY`.

## Provider Quality

Deterministic stub provider result:

- total cases: `6`
- passed cases: `6`
- failed cases: `0`
- CUDA regression cases: `cuda_async_default_stream`, `cuda_cooperative_groups_grid_sync`

Command:

```bash
cd /home/et16/work/review_system/review-bot
uv run python -m review_bot.cli.evaluate_provider_quality --provider stub
```

OpenAI no-key behavior:

- status: `skipped`
- skip reason: `OPENAI_API_KEY is not set`

## Density Contract

Fixture-level contract:

- `maximum_review_comments`: `5`
- `minimum_distinct_comment_paths`: `2`
- `maximum_comments_per_path`: `2`

Covered fixtures:

- `synthetic-mixed-language`
- `curated-polyglot`
- `cuda-targeted`

The contract is validated by `tests/test_multilang_smoke_fixture.py` without starting local GitLab.
The live smoke script applies the same contract to GitLab discussion positions after bot publication.

## Validation

Commands completed successfully:

```bash
cd /home/et16/work/review_system/review-bot
uv run pytest tests/test_multilang_smoke_fixture.py tests/test_provider_quality.py tests/test_prompting.py tests/test_review_runner.py::test_review_runner_suppresses_same_line_same_category_variants_before_batch_selection -q
uv run ruff check ../ops/scripts/smoke_local_gitlab_multilang_review.py tests/test_multilang_smoke_fixture.py review_bot/cli/evaluate_provider_quality.py review_bot/quality/provider_quality.py tests/test_provider_quality.py
cd /home/et16/work/review_system
bash ops/scripts/smoke_local_gitlab_multilang_review.sh --fixture synthetic-mixed-language --json-output /tmp/review-bot-multilang-smoke-batch5.json
```

Results:

- pytest: `26 passed`
- ruff: `All checks passed`
- JSON fixtures: `python3 -m json.tool` passed for all smoke `expected_smoke.json` files.
- live synthetic smoke: `next_batch_size=5`, `bot_comment_count=4`, `distinct_comment_paths=3`.
