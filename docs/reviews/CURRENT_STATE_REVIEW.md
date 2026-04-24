# Current State Review

## Purpose

이 문서는 `docs/REVIEW_ROADMAP.md`를 따라 누적되는 현재 상태 리뷰 본문이다.
각 review unit은 findings-first 형식으로 이 문서를 갱신한다.

## Review Status

- `2026-04-24` 기준 review frame과 evidence inventory를 먼저 고정했다.
- 이번 unit은 산출물 형식 정리만 수행했고, 아직 substantive finding은 누적하지 않았다.
- 이후 unit은 아래 scope, validation mode, finding contract를 그대로 재사용한다.

## Review Scope And Evidence Inventory

| Area | Primary question | Core evidence | Default validation mode |
| --- | --- | --- | --- |
| Architecture and canonical invariants | 문서가 말하는 canonical boundary와 실제 코드 책임이 일치하는가 | [README.md](/home/et16/work/review_system/README.md:1), [docs/CURRENT_SYSTEM.md](/home/et16/work/review_system/docs/CURRENT_SYSTEM.md:1), [docs/API_CONTRACTS.md](/home/et16/work/review_system/docs/API_CONTRACTS.md:1), [AGENTS.md](/home/et16/work/review_system/AGENTS.md:1) | 정적 읽기 우선 |
| `review-engine` boundary | rule source, policy, ingest, retrieval, lifecycle CLI가 canonical YAML 경계를 지키는가 | [docs/CURRENT_SYSTEM.md](/home/et16/work/review_system/docs/CURRENT_SYSTEM.md:1), [review-engine/review_engine/ingest/rule_loader.py](/home/et16/work/review_system/review-engine/review_engine/ingest/rule_loader.py:1), [review-engine/review_engine/cli/rule_lifecycle.py](/home/et16/work/review_system/review-engine/review_engine/cli/rule_lifecycle.py:1), [review-engine/tests/test_rule_lifecycle_cli.py](/home/et16/work/review_system/review-engine/tests/test_rule_lifecycle_cli.py:1) | 정적 읽기 후 필요 시 targeted test |
| `review-bot` lifecycle and UX | detect/publish/sync/verify와 note command surface가 과도하게 섞이지 않았는가 | [docs/CURRENT_SYSTEM.md](/home/et16/work/review_system/docs/CURRENT_SYSTEM.md:1), [review-bot/review_bot/bot/review_runner.py](/home/et16/work/review_system/review-bot/review_bot/bot/review_runner.py:1), [review-bot/review_bot/review_systems/gitlab.py](/home/et16/work/review_system/review-bot/review_bot/review_systems/gitlab.py:1), [review-bot/review_bot/api/main.py](/home/et16/work/review_system/review-bot/review_bot/api/main.py:1) | 정적 읽기 후 필요 시 targeted test |
| Ops, smoke, automation | smoke와 automation이 실제 gate인지, 아니면 참고 신호인지 명확한가 | [docs/OPERATIONS_RUNBOOK.md](/home/et16/work/review_system/docs/OPERATIONS_RUNBOOK.md:1), [ops/scripts/smoke_local_gitlab_lifecycle_review.sh](/home/et16/work/review_system/ops/scripts/smoke_local_gitlab_lifecycle_review.sh:1), [ops/scripts/smoke_openai_provider_direct.sh](/home/et16/work/review_system/ops/scripts/smoke_openai_provider_direct.sh:1), [ops/scripts/advance_roadmap_with_codex.sh](/home/et16/work/review_system/ops/scripts/advance_roadmap_with_codex.sh:1) | 정적 읽기 후 필요 시 runtime evidence |
| Docs/runtime consistency | canonical docs와 실제 코드/스크립트/기본값이 어긋나지 않는가 | [README.md](/home/et16/work/review_system/README.md:1), [docs/CURRENT_SYSTEM.md](/home/et16/work/review_system/docs/CURRENT_SYSTEM.md:1), [docs/API_CONTRACTS.md](/home/et16/work/review_system/docs/API_CONTRACTS.md:1), [docs/OPERATIONS_RUNBOOK.md](/home/et16/work/review_system/docs/OPERATIONS_RUNBOOK.md:1), [ops/.env.example](/home/et16/work/review_system/ops/.env.example:1) | 정적 읽기 우선 |
| Dead weight and compatibility leftovers | 남길 이유가 약한 wrapper, compat path, stale doc가 남아 있는가 | [docs/ROADMAP.md](/home/et16/work/review_system/docs/ROADMAP.md:1), [ops/scripts/smoke_local_gitlab_tde_review.sh](/home/et16/work/review_system/ops/scripts/smoke_local_gitlab_tde_review.sh:1), [ops/scripts/advance_review_roadmap_with_codex.sh](/home/et16/work/review_system/ops/scripts/advance_review_roadmap_with_codex.sh:1) | 정적 읽기 우선 |

## Validation Modes

| Signal | Static read is enough when | Execution is required when | Canonical validation |
| --- | --- | --- | --- |
| 문서/계약 일치성 | 문구, canonical invariant, naming drift, dead wrapper 여부를 판단할 때 | 실행 결과를 근거로 해야만 모순 여부가 드러날 때 | `git diff --check` |
| Targeted unit or integration test | 구조상 어떤 동작이 의도인지 판단할 때 | queue, adapter, lifecycle, CLI behavior를 실제로 확인해야 할 때 | `cd review-engine && uv run pytest ... -q`, `cd review-bot && uv run pytest ... -q` |
| Local GitLab lifecycle smoke | script와 docs의 책임 경계를 읽는 것만으로 충분할 때 | GitLab webhook head race, thread sync, incremental replay 신뢰성을 주장할 때 | `bash /home/et16/work/review_system/ops/scripts/smoke_local_gitlab_lifecycle_review.sh` |
| Provider-direct smoke | provider fallback policy만 문서로 확인할 때 | live OpenAI 또는 OpenAI-compatible endpoint direct success/failure를 증거로 남겨야 할 때 | `bash /home/et16/work/review_system/ops/scripts/smoke_openai_provider_direct.sh` |

판단 규칙:

- lifecycle smoke와 provider-direct smoke는 다른 신호로 취급한다.
- fallback이 켜진 lifecycle smoke 성공만으로 live OpenAI success를 주장하지 않는다.
- 문서 중심 review unit은 정적 읽기와 `git diff --check`만으로 닫을 수 있다.

## Executive Summary

- review frame, evidence inventory, validation split, finding contract를 먼저 고정했다.
- substantive architecture, runtime, cleanup finding은 이후 unit에서 누적한다.

## Finding Contract

모든 finding은 아래 네 필드를 반드시 포함한다.

- `Severity`: 사용자 영향, 운영 위험, 잘못된 의사결정 가능성을 기준으로 `critical`, `high`, `medium`, `low` 중 하나를 사용한다.
- `Evidence`: 실제 근거가 되는 파일, 명령, 출력, 문서 불일치 지점을 적는다.
- `Impact`: 왜 이 finding이 중요한지, 무엇이 잘못될 수 있는지 적는다.
- `Action`: 즉시 수정, 후속 roadmap, deferred 유지, keep-as-is 중 하나로 명시한다.

권장 기록 형식:

```md
### F-<area>-NN <short title>
- Severity: `medium`
- Evidence: [path/to/file](/abs/path:1), command `...`, observed mismatch `...`
- Impact: <user, operator, or maintenance risk>
- Action: <direct fix | roadmap follow-up | defer with reason | keep as-is with reason>
```

## Findings

- 현재 없음. 이후 review unit부터 위 contract로 누적한다.

## Direction Check

- 이번 unit에서는 방향성 결론을 내리지 않았다.
- 다음 unit에서 canonical docs와 architecture boundary를 기준으로 1차 결론을 남긴다.

## Roadmap / Deferred Assessment

- 이번 unit에서는 roadmap 재배치 판단을 하지 않았다.
- 후속 review에서 action이 필요한 finding만 backlog와 roadmap/deferred 판단으로 연결한다.

## Recommended Actions

- 이후 review unit은 먼저 이 문서에 finding을 남기고, 실행이 필요한 항목만 별도 validation으로 승격한다.
- 후속 조치가 필요한 finding만 `docs/reviews/REVIEW_FINDINGS_BACKLOG.md`에 옮긴다.
