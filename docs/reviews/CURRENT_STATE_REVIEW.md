# Current State Review

## Purpose

이 문서는 `docs/REVIEW_ROADMAP.md`를 따라 누적되는 현재 상태 리뷰 본문이다.
각 review unit은 findings-first 형식으로 이 문서를 갱신한다.

## Review Status

- `2026-04-24` 기준 review frame과 evidence inventory를 먼저 고정했다.
- 같은 날짜 architecture and direction review를 추가로 수행했고, top-level boundary 결론과 legacy compatibility drift를 누적했다.
- 같은 날짜 `review-engine` deep review를 추가로 수행했고, canonical YAML write boundary 강점과 extension identity collision 리스크를 누적했다.
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

- external Git review system을 canonical UI로 두고 `review-bot`이 `detect -> publish -> sync` lifecycle을 책임지는 현재 방향은 여전히 일관된다.
- 가장 큰 drift는 구조 방향 자체보다 local harness compatibility residue다. `review-platform` bot facade는 current-state에서 제거됐다고 적은 legacy `pr_id` bot endpoint를 아직 호출하고, 테스트는 이 경계를 mock으로만 덮는다.
- `ReviewRunner`와 `local_platform` adapter 안에도 `_legacy_key`, `BOT_LEGACY_*`, `pr_id` helper가 남아 있어 문서가 말하는 canonical `ReviewRequestKey` boundary보다 구현이 더 느슨하다.
- `review-engine` 쪽은 source atom coverage matrix, model validator, minimal lifecycle CLI가 canonical YAML write boundary를 꽤 잘 지키고 있다.
- 다만 extension rule root에 같은 `pack_id` 또는 `policy_id`가 들어오면 runtime loader와 lifecycle CLI가 마지막 항목으로 조용히 덮어써서, 문서가 말하는 canonical identity/fail-fast 규칙보다 구현이 느슨하다.
- manual editor는 지금 끌어올릴 시점이 아니다. 먼저 extension identity collision을 명시적 오류로 바꾸고, canonical file path와 source-atom maintenance를 더 선명하게 드러내는 편이 맞다.

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

### F-arch-01 Local harness bot facade still depends on removed legacy `pr_id` review-bot endpoints
- Severity: `medium`
- Evidence: [docs/API_CONTRACTS.md](/home/et16/work/review_system/docs/API_CONTRACTS.md:1)는 current-state에서 legacy `pr_id` endpoint가 제거됐다고 적지만, [review-platform/app/clients/bot_client.py](/home/et16/work/review_system/review-platform/app/clients/bot_client.py:12)는 여전히 `/internal/review/pr-updated`, `/internal/review/next-batch`, `/internal/review/state/{pr_id}`를 호출한다. 반면 [review-bot/review_bot/api/main.py](/home/et16/work/review_system/review-bot/review_bot/api/main.py:81)는 key 기반 `/internal/review/runs`, `/internal/review/runs/{run_id}/publish`, `/internal/review/requests/{review_system}/{project_ref}/{review_request_id}`만 노출한다. [review-platform/tests/test_pr_flow.py](/home/et16/work/review_system/review-platform/tests/test_pr_flow.py:189)는 이 경계를 실제 bot API 대신 `mock_bot`으로 검증한다.
- Impact: local harness가 current-state 계약과 실제로 연결되어 있다고 믿기 쉽지만, 실제 wiring은 stale or broken 상태일 수 있다. 이는 local demo와 integration confidence를 약하게 만들고, architecture review에서 harness evidence를 과신하게 만든다.
- Action: `direct fix`

### F-arch-02 Canonical `ReviewRequestKey` boundary is still blurred by runner-level legacy compatibility helpers
- Severity: `medium`
- Evidence: [review-bot/review_bot/bot/review_runner.py](/home/et16/work/review_system/review-bot/review_bot/bot/review_runner.py:261)는 `run_review`, `create_review_run`, `publish_next_batch`, `build_state`에서 `pr_id` 기반 compatibility path를 유지하고, 같은 파일의 [legacy key helper](/home/et16/work/review_system/review-bot/review_bot/bot/review_runner.py:3448)는 `BOT_LEGACY_REVIEW_SYSTEM`, `BOT_LEGACY_PROJECT_REF`를 사용한다. [review-bot/review_bot/config.py](/home/et16/work/review_system/review-bot/review_bot/config.py:106)는 이 legacy 설정을 current config surface에 남겨 두고, [review-bot/review_bot/review_systems/local_platform.py](/home/et16/work/review_system/review-bot/review_bot/review_systems/local_platform.py:133)는 local harness용 `review_request_id` integer helper를 계속 제공한다.
- Impact: 문서 기준의 canonical business identity는 `ReviewRequestKey`로 정리됐지만, 실제 runner core는 아직 legacy identity shim을 품고 있다. 이 상태는 harness/test convenience가 production lifecycle code에 남아 있게 만들어 이후 cleanup과 API 경계 단순화를 더 어렵게 한다.
- Action: `roadmap follow-up`

### F-arch-03 Core architecture direction still matches the documented operating model
- Severity: `low`
- Evidence: [README.md](/home/et16/work/review_system/README.md:1), [docs/CURRENT_SYSTEM.md](/home/et16/work/review_system/docs/CURRENT_SYSTEM.md:1), [docs/API_CONTRACTS.md](/home/et16/work/review_system/docs/API_CONTRACTS.md:1)는 공통으로 외부 Git review system을 canonical UI로 두고 `review-bot`이 lifecycle을 책임지며 `review-platform`은 harness라고 정의한다. 이 방향은 [review-bot/review_bot/api/main.py](/home/et16/work/review_system/review-bot/review_bot/api/main.py:81)의 key-based run/state/full-report API와 [review-bot/review_bot/api/main.py](/home/et16/work/review_system/review-bot/review_bot/api/main.py:210)의 GitLab note-first trigger 처리에서 그대로 구현돼 있다.
- Impact: deep review 단계는 top-level 방향 자체를 다시 뒤집기보다, current-state 문서와 남은 compatibility residue의 간극을 줄이는 쪽에 집중하면 된다.
- Action: `keep as-is with reason`

### F-engine-01 Extension rule root identity collisions silently overwrite prior pack or policy definitions
- Severity: `medium`
- Evidence: [docs/CURRENT_SYSTEM.md](/home/et16/work/review_system/docs/CURRENT_SYSTEM.md:126)는 extension rule root 오류를 fail-fast 하며 `pack_id`를 canonical identity로 다룬다고 적지만, [review-engine/review_engine/ingest/rule_loader.py](/home/et16/work/review_system/review-engine/review_engine/ingest/rule_loader.py:69)는 resolved root를 순회하면서 `pack_index[pack.pack_id]`와 `policy_index[policy.policy_id]`에 마지막 값을 그대로 대입한다. [review-engine/review_engine/cli/rule_lifecycle.py](/home/et16/work/review_system/review-engine/review_engine/cli/rule_lifecycle.py:728)도 inspection/mutation 경로에서 같은 방식으로 available pack index를 구성한다. 반면 현재 targeted regression은 [review-engine/tests/test_rule_runtime.py](/home/et16/work/review_system/review-engine/tests/test_rule_runtime.py:267)의 noncanonical conflict surface 거부와 [review-engine/tests/test_rule_lifecycle_cli.py](/home/et16/work/review_system/review-engine/tests/test_rule_lifecycle_cli.py:561)의 merged profile write boundary 거부까지는 덮지만, duplicate identity collision 자체를 명시적으로 검증하지 않는다.
- Impact: public root와 extension root, 또는 extension root끼리 같은 `pack_id`/`policy_id`를 재사용하면 어떤 정의가 실제 runtime과 lifecycle CLI에서 선택됐는지 조용히 바뀔 수 있다. 이 상태는 authoring 실수나 packaging drift를 늦게 발견하게 만들고, `disable`/`enable` 같은 최소 mutation 도구도 ambiguous identity를 드러내지 못하게 만든다.
- Action: `direct fix`

### F-engine-02 Minimal lifecycle CLI and source coverage matrix preserve the canonical YAML write boundary
- Severity: `low`
- Evidence: [docs/CURRENT_SYSTEM.md](/home/et16/work/review_system/docs/CURRENT_SYSTEM.md:146)는 lifecycle CLI mutation이 single canonical pack/profile YAML만 수정해야 한다고 고정하고, [review-engine/review_engine/models.py](/home/et16/work/review_system/review-engine/review_engine/models.py:111)와 [review-engine/review_engine/models.py](/home/et16/work/review_system/review-engine/review_engine/models.py:176)는 noncanonical conflict surface를 모델 단계에서 거부한다. 이 경계는 [review-engine/tests/test_rule_lifecycle_cli.py](/home/et16/work/review_system/review-engine/tests/test_rule_lifecycle_cli.py:362)의 canonical profile YAML-only mutation, [review-engine/tests/test_rule_lifecycle_cli.py](/home/et16/work/review_system/review-engine/tests/test_rule_lifecycle_cli.py:561)의 merged profile write boundary fail-fast, [review-engine/tests/test_source_coverage_matrix.py](/home/et16/work/review_system/review-engine/tests/test_source_coverage_matrix.py:60)의 source atom coverage completeness 검증으로 계속 고정된다.
- Impact: generated dataset나 merged runtime state를 직접 수정하는 우회 surface 없이, canonical YAML과 source atom inventory를 기준으로 운영한다는 현재 rule authoring 원칙은 여전히 방어 가능하다.
- Action: `keep as-is with reason`

### F-engine-03 Manual editor should stay deferred until authoring boundary evidence is tighter
- Severity: `low`
- Evidence: [docs/deferred/rule_authoring_and_editor.md](/home/et16/work/review_system/docs/deferred/rule_authoring_and_editor.md:12)는 editor/UI를 미루는 이유로 rule state model, validation, public/private extension boundary 정리를 먼저 요구한다. 실제 코드도 [review-engine/review_engine/cli/rule_lifecycle.py](/home/et16/work/review_system/review-engine/review_engine/cli/rule_lifecycle.py:740)에서 single profile write boundary가 없으면 pack mutation을 거부하고, [review-engine/tests/test_source_coverage_matrix.py](/home/et16/work/review_system/review-engine/tests/test_source_coverage_matrix.py:60)는 source coverage가 source atom 단위까지 완결돼야 함을 강제한다. 여기에 `F-engine-01`의 duplicate identity collision이 아직 unresolved다.
- Impact: 지금 editor를 올리면 public/shared/extension root 중 어디를 수정하는지, source atom coverage와 canonical YAML이 어떻게 함께 유지되는지 UI가 대신 추론해야 한다. 그 결과 별도 저장 모델이나 숨은 write path가 다시 생길 가능성이 높다.
- Action: `defer with reason`

## Direction Check

- top-level 방향성은 맞다. external review system canonical UI, `review-bot` lifecycle ownership, `review-platform` harness-only positioning은 문서와 핵심 코드가 일치한다.
- 다만 local harness와 runner 내부에 남은 legacy `pr_id` compatibility seam 때문에 current-state 문서보다 구현 경계가 더 넓다.
- `review-engine`도 큰 방향은 맞다. source atom coverage matrix, model validator, minimal lifecycle CLI는 canonical YAML boundary를 유지하는 데 실제로 기여하고 있다.
- `review-engine`에서 줄여야 할 표면은 editor 부재가 아니라 duplicate pack/policy identity를 조용히 허용하는 부분이다.
- 이후 deep review는 구조 전환 제안보다, stale harness contract, runner compatibility residue, engine identity collision 같은 느슨한 seam을 줄이는 관점으로 진행하는 편이 맞다.

## Roadmap / Deferred Assessment

- `F-arch-01`은 review 단위 backlog를 넘어 실제 direct fix 후보다. local harness가 current API를 따라가도록 바꾸거나 unsupported path를 명시적으로 닫아야 한다.
- `F-arch-02`는 harness migration 이후 `docs/ROADMAP.md` 또는 cleanup review에서 다룰 후속 항목으로 남기는 편이 안전하다.
- `F-engine-01`은 `review-engine` 내부 direct fix 후보다. runtime loader와 lifecycle CLI가 resolved root 간 duplicate `pack_id`/`policy_id`를 명시적 ambiguity로 fail-fast 하도록 맞추는 편이 맞다.
- `F-engine-03`은 deferred에 그대로 남겨야 한다. duplicate identity guard와 authoring path evidence가 더 쌓이기 전에는 manual editor를 active roadmap으로 끌어올릴 이유가 약하다.

## Recommended Actions

- `review-platform` bot facade를 current key-based `review-bot` API에 맞추고, mock이 아닌 contract test를 하나 추가한다.
- harness migration 뒤에는 runner core의 `_legacy_key`, `BOT_LEGACY_*`, `pr_id` helper를 test-only shim 또는 명시적 compatibility layer로 밀어낸다.
- `review-engine` loader와 lifecycle CLI에 duplicate pack/policy identity collision guard를 넣고, public+extension 및 extension+extension collision regression을 추가한다.
- manual editor/editor UI는 deferred에 유지하고, 대신 canonical file path preview와 authoring failure evidence를 나중에 별도 수집한다.
- 다음 review unit은 `review-bot` deep review로 넘어가되, local harness evidence는 `F-arch-01` 해결 전까지 current-state runtime proof로 과신하지 않는다.
