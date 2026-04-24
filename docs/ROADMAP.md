# Roadmap

## Purpose

이 문서는 지금 바로 실행할 수 있는 작업만 관리한다.
이미 끝난 기반 설명은 [CURRENT_SYSTEM.md](/home/et16/work/review_system/docs/CURRENT_SYSTEM.md:1)에 두고,
완료된 roadmap 이력은 git history와 [CURRENT_STATE_REVIEW.md](/home/et16/work/review_system/docs/reviews/CURRENT_STATE_REVIEW.md:1)에 둔다.
외부 계정, live provider quota, 사람 승인, 별도 repository 권한이 필요한 작업은 실행 조건이 준비될 때까지
`docs/deferred/*.md`에 남긴다.

마지막 코드 상태 점검일: `2026-04-24`

상태 표기:

- `active`: 지금 바로 commit 단위로 진행할 수 있다.
- `queued`: 앞선 `active` 항목이 끝나면 바로 착수할 다음 후보다.
- `watch`: 구현보다 회귀 방지와 운영 관찰이 중심이다.

운영 원칙:

- 한 roadmap unit은 가능하면 한 commit에서 닫는다.
- 아래 `###` 항목 하나가 `advance_roadmap_with_codex.sh`의 한 iteration에서 고를 수 있는 최소 실행 단위다.
- 한 iteration에서 두 개 이상의 `###` 항목을 묶지 않는다.
- `active` 항목을 roadmap order대로 먼저 처리한다.
- `queued` 항목은 앞선 관련 `active` 항목이 완료되거나 blocked로 기록된 뒤 처리한다.
- blocked이면 final output의 `BLOCKED_UNIT`에 아래 heading을 그대로 쓴다.

## Current Snapshot

`2026-04-24` `gpt-5.5` 리뷰 라운드 이후 post-review immediate fixes, cleanup,
contract readiness packet은 닫혔다. 현재 roadmap에는 완료 항목을 반복 노출하지 않고,
외부 조건 없이 시작 가능한 slice가 생길 때만 `Now`에 올린다.

닫힌 기반:

- 기존 Git review surface 중심 제품 방향
- canonical `ReviewRequestKey(review_system, project_ref, review_request_id)` identity
- runner-owned `detect -> publish -> sync` lifecycle boundary
- immutable lifecycle event-backed analytics direction
- bounded `review-bot` / `review-platform` TestClient gates
- bounded OpenAI direct smoke preflight
- lifecycle provider runtime provenance: provider, fallback, configured model, sanitized endpoint,
  transport class
- GitLab stale-head retryable detect failure guardrail
- request-scoped adapter thread/feedback identity
- local harness key-based bot bridge
- strict canonical YAML unknown-key rejection
- duplicate/missing selected pack fail-fast
- default profile fallback semantics
- canonical rule reverse source coverage
- private rule package manifest validation CLI, strict `package.yaml` metadata model, sample package fixture
- private rule package split validation gate with package-specific private artifact boundary,
  runtime retrieval, public-only regression, and deterministic JSON summary
- private rule package install plan output with versioned runtime root, private artifact root,
  dataset path, collection preview, and pointer-only update/rollback plan
- private rule packaging, manual editor, provider tuning, multi-SCM, auto-fix readiness packets
- CLI-first rule authoring validation preview command with strict canonical YAML validation,
  selected pack/profile resolution, source coverage guardrail, and read-only ingest/retrieval
  impact summary

현재 즉시 실행 가능한 방향:

- 없음. 다음 executable slice는 deferred 조건이 준비되면 `Now`에 올린다.

현재 바로 실행하지 않는 방향:

- provider/ranking/density tuning: OpenAI quota, live direct smoke success, comparison artifact,
  human review decision이 필요하다.
- GitHub/Multi-SCM adapter: test repository, token/permissions, webhook 또는 replay fixture가 필요하다.
- auto-fix/apply: trust metric, low-risk fix class, reviewer approval, audit, rollback evidence가 필요하다.

## Now

현재 `active` / `queued` 실행 단위는 없다.

## Deferred But Not Yet Executable

아래 항목은 readiness packet은 있지만, 현재 automation이 바로 구현하면 조건을 채울 수 없다.
조건이 준비되면 이 문서의 `Now`에 새 `active` unit으로 올린다.

- Provider / ranking / density tuning
  - 필요 조건: quota/billing 정상 OpenAI API key, `--expect-live-openai` direct smoke 성공,
    provider quality/comparison artifact, human comparison decision
  - owner: [provider_and_model_work.md](/home/et16/work/review_system/docs/deferred/provider_and_model_work.md:1)
- GitHub / Multi-SCM adapter expansion
  - 필요 조건: GitHub test repository, GitHub App 또는 token permissions, webhook/replay fixture,
    live smoke artifact policy
  - owner: [platform_expansion.md](/home/et16/work/review_system/docs/deferred/platform_expansion.md:1)
- Auto-fix / apply automation
  - 필요 조건: trust metric baseline, low-risk fix class evidence, reviewer approval/audit/rollback validation
  - owner: [automation_work.md](/home/et16/work/review_system/docs/deferred/automation_work.md:1)

## Watch

아래 영역은 현재 roadmap의 직접 구현 대상이 아니다.

- Existing Git review surface 중심 제품 방향
- Canonical `ReviewRequestKey` identity
- Runner-owned lifecycle boundary
- Event-backed lifecycle analytics direction
- Current six-command note UX
- Local GitLab smoke와 direct provider smoke를 별도 evidence로 보는 운영 원칙

변경이 생기면 여기서 다시 `active`로 올린다.

## Validation Baseline

문서/계약 작업:

```bash
git diff --check
bash -n ops/scripts/advance_roadmap_with_codex.sh ops/scripts/advance_review_roadmap_with_codex.sh
```

`review-engine` rule / package / lifecycle contract 변경:

```bash
cd review-engine && uv run pytest tests/test_rule_runtime.py tests/test_rule_lifecycle_cli.py -q
cd review-engine && uv run pytest tests/test_rule_runtime_private_extension.py tests/test_source_coverage_matrix.py -q
```

`review-bot` contract 변경:

```bash
cd review-bot && uv run pytest tests/test_review_runner.py -q
cd review-bot && uv run pytest tests/test_api_queue.py -q
```

`review-platform` harness 변경:

```bash
cd review-platform && uv run pytest tests/test_health.py tests/test_pr_flow.py -q
```

local smoke와 direct provider validation은 해당 작업이 실제 runtime/adapter/provider 경로를 건드릴 때만 추가한다.
