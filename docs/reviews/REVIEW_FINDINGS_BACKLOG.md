# Review Findings Backlog

## Purpose

이 문서는 `docs/reviews/CURRENT_STATE_REVIEW.md`에서 나온 후속 작업 후보를 모은다.

## Intake Rule

- backlog entry는 반드시 `CURRENT_STATE_REVIEW.md`의 finding 하나를 참조해야 한다.
- review 본문에서 `Action`이 `direct fix`, `roadmap follow-up`, `defer with reason` 중 하나일 때만 backlog로 승격한다.
- backlog는 리뷰 서술이 아니라 후속 실행 단위 정리 문서다.

## Field Contract

- `Finding`: 원문 finding id와 제목
- `Severity`: review 본문과 동일한 severity
- `Area`: `review-engine`, `review-bot`, `ops`, `docs`, `cross-cutting` 중 하나
- `Evidence`: backlog를 만든 직접 근거
- `Recommended action`: 다음에 실제로 해야 할 일
- `Follow-up target`: `direct fix`, `docs/ROADMAP.md`, `deferred`, `needs decision`
- `Validation note`: 후속 작업이 필요로 할 검증 또는 현재 생략 사유

## Backlog Entry Template

```md
### B-<area>-NN <short action title>
- Finding: `F-<area>-NN <short title>`
- Severity: `high`
- Area: `review-bot`
- Evidence: [path/to/file](/abs/path:1), command `...`, observed mismatch `...`
- Recommended action: <concrete next step>
- Follow-up target: `direct fix`
- Validation note: <test or smoke to run later, or why none is needed>
```

## Backlog

### B-cross-01 Rewire local harness bot facade to the current key-based review-bot API
- Finding: `F-arch-01 Local harness bot facade still depends on removed legacy pr_id review-bot endpoints`
- Severity: `medium`
- Area: `cross-cutting`
- Evidence: [docs/API_CONTRACTS.md](/home/et16/work/review_system/docs/API_CONTRACTS.md:1), [review-platform/app/clients/bot_client.py](/home/et16/work/review_system/review-platform/app/clients/bot_client.py:12), [review-bot/review_bot/api/main.py](/home/et16/work/review_system/review-bot/review_bot/api/main.py:81), [review-platform/tests/test_pr_flow.py](/home/et16/work/review_system/review-platform/tests/test_pr_flow.py:189)
- Recommended action: `review-platform`이 `ReviewRequestKey(review_system=local_platform, project_ref=local/default, review_request_id=<pr_id>)`를 사용해 current `review-bot` API를 호출하도록 바꾼다. review trigger는 `POST /internal/review/runs`, next-batch는 latest run 조회 후 `/internal/review/runs/{run_id}/publish`, state는 `/internal/review/requests/local_platform/local/default/{pr_id}`로 읽게 맞춘다.
- Follow-up target: `direct fix`
- Validation note: `cd review-platform && uv run pytest tests/test_pr_flow.py -q`에 더해 mock 없이 current `review-bot` route shape를 검증하는 targeted contract test가 필요하다. local GitLab smoke, provider-direct smoke, direct OpenAI 검증은 이 항목 범위 밖이다.

### B-cross-02 Retire runner-side legacy identity helpers after the harness path is ported
- Finding: `F-arch-02 Canonical ReviewRequestKey boundary is still blurred by runner-level legacy compatibility helpers`
- Severity: `medium`
- Area: `cross-cutting`
- Evidence: [review-bot/review_bot/bot/review_runner.py](/home/et16/work/review_system/review-bot/review_bot/bot/review_runner.py:261), [review-bot/review_bot/bot/review_runner.py](/home/et16/work/review_system/review-bot/review_bot/bot/review_runner.py:3448), [review-bot/review_bot/config.py](/home/et16/work/review_system/review-bot/review_bot/config.py:106), [review-bot/review_bot/review_systems/local_platform.py](/home/et16/work/review_system/review-bot/review_bot/review_systems/local_platform.py:133)
- Recommended action: local harness와 older test caller를 current key-based API로 옮긴 뒤, `ReviewRunner` public helper에서 `pr_id` compatibility를 제거하거나 test-only shim으로 격리한다. 같은 시점에 `BOT_LEGACY_REVIEW_SYSTEM`, `BOT_LEGACY_PROJECT_REF`를 current-state 운영 surface에서 내린다.
- Follow-up target: `docs/ROADMAP.md`
- Validation note: runner와 local adapter targeted test를 `ReviewRequestKey` 중심으로 바꾼 뒤 `cd review-bot && uv run pytest tests/test_review_runner.py tests/test_integration_phase1_4.py -q`로 회귀를 확인한다. local GitLab smoke와 provider-direct smoke는 직접 필요하지 않다.
