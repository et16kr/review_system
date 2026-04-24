# Review Findings Backlog

## Purpose

이 문서는 `docs/reviews/CURRENT_STATE_REVIEW.md`에서 나온 `gpt-5.5` 리뷰 후속 작업 후보를 모은다.
이전 리뷰 라운드의 backlog는 git history에 남아 있으며, 현재 문서는 새 라운드 기준으로 다시 채운다.

## Intake Rule

- backlog entry는 반드시 `CURRENT_STATE_REVIEW.md`의 finding 하나를 참조한다.
- `Action`이 `direct fix`, `roadmap follow-up`, `defer with reason`, `remove`, `needs decision` 중 하나일 때만 backlog에 올린다.
- backlog는 리뷰 서술이 아니라 후속 실행 단위 정리 문서다.

## Field Contract

- `Finding`: 원문 finding id와 제목
- `Severity`: review 본문과 동일한 severity
- `Area`: `review-engine`, `review-bot`, `review-platform`, `ops`, `docs`, `cross-cutting` 중 하나
- `Evidence`: backlog를 만든 직접 근거
- `Recommended action`: 다음에 실제로 해야 할 일
- `Follow-up target`: `direct fix`, `docs/ROADMAP.md`, `deferred`, `remove`, `needs decision`
- `Post-review bucket`: `bug_fix`, `roadmap_update`, `deferred_update`, `remove`, `keep`, `needs_decision` 중 하나
- `Validation note`: 후속 작업이 필요로 할 검증 또는 현재 생략 사유

## Backlog Entry Template

```md
### B-<area>-NN <short action title>
- Finding: `F-<area>-NN <short title>`
- Severity: `medium`
- Area: `review-bot`
- Evidence: [path/to/file](/abs/path:1), command `...`, observed mismatch `...`
- Recommended action: <concrete next step>
- Follow-up target: `direct fix`
- Post-review bucket: `bug_fix`
- Validation note: <test or smoke to run later, or why none is needed>
```

## Backlog

아직 작성 전.
