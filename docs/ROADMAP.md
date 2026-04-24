# Roadmap

## Purpose

이 문서는 지금 바로 실행할 수 있는 작업만 관리한다.
이미 끝난 기반 설명은 [CURRENT_SYSTEM.md](/home/et16/work/review_system/docs/CURRENT_SYSTEM.md:1)에 두고,
직접 착수할 수 없는 장기 작업은 `docs/deferred/*.md`에 둔다.

마지막 코드 상태 점검일: `2026-04-24`

상태 표기:

- `active`: 지금 바로 commit 단위로 진행할 수 있다.
- `partial`: 일부 기반은 있지만 남은 실행 단위가 있다.
- `queued`: 선행 작업이 끝나면 바로 착수할 다음 후보다.
- `watch`: 구현보다 회귀 방지와 운영 관찰이 중심이다.

운영 원칙:

- external API quota, 사람 승인, 별도 계정 권한이 필요한 작업은 본 문서의 직접 실행 항목으로 두지 않는다.
- 한 roadmap unit은 가능하면 한 commit에서 닫는다.
- 문서만 정리하는 작업도, 다음 구현을 실제로 열어 주는 경우에만 roadmap에 둔다.

## Current Snapshot

현재는 아래 기반이 이미 닫혔고, 새 구현 대상은 아니다.

- Provider runtime guardrails
- Smoke / evaluation hardening
- Organization rule extension canonicalization
- Roadmap automation blocked artifact retention
- Minimal rule lifecycle CLI

즉 지금 남은 핵심은:

1. 다음 rule expansion slice를 고를 수 있게 evidence 경로를 다시 고정하는 일
2. `.review-bot.yaml` / `ask`처럼 아직 product boundary가 모호한 UX surface의 선행 계약을 정리하는 일
3. local backend 실험을 실제 retained artifact capture로 이어 가기 전 준비를 끝내는 일
4. deferred 장기 작업에 들어가기 전 필요한 사전 작업을 문서와 작은 검증 경로로 닫는 일

## Now

### 1. Evidence Refresh Path For Targeted Rule Expansion

상태: `active`

왜 지금 하나:

- `Targeted Rule Expansion` 자체는 여전히 가치가 크지만,
  지금은 다음 gap을 고를 fresh evidence 경로가 불안정해서 automation이 blocker로 끝난다.
- 다음 rule slice보다 먼저, evidence refresh 절차를 repo-local 기준으로 다시 고정해야 한다.

이번 작업의 범위:

1. 다음 rule 후보를 고를 때 어떤 근거를 우선하는지 순서를 고정한다.
   - repo-local retained artifact
   - local analytics endpoint
   - local smoke artifact
2. endpoint가 비어 있거나 local GitLab이 꺼져 있어도,
   automation이 “왜 막혔는지”를 같은 형식으로 남기게 한다.
3. fresh evidence가 없을 때 임의로 다음 rule family를 고르지 않도록,
   checkpoint freshness 기준과 artifact 위치를 문서로 고정한다.

완료 기준:

- 다음 under-trigger gap을 고르는 입력 경로가 문서와 automation에서 같은 순서를 쓴다.
- 환경이 비어 있을 때도 blocker가 재현 가능하게 기록된다.
- 이후 `Targeted Rule Expansion`은 evidence refresh 때문에 다시 product ambiguity blocker로 멈추지 않는다.

### 2. `.review-bot.yaml` Contract Definition

상태: `active`

왜 지금 하나:

- `.review-bot.yaml` 구현 자체보다,
  policy / env / note command precedence가 아직 모호해서 실행 단위로 닫히지 않는다.
- 이 계약을 먼저 고정해야 implementation이 다시 blocker 없이 이어진다.

이번 작업의 범위:

1. `.review-bot.yaml`이 다루는 최소 surface를 정의한다.
2. env, repo config, note command 중 무엇이 우선하는지 precedence 표를 고정한다.
3. 허용하지 않을 값과 fail-fast / ignore / warn 경계를 정한다.
4. `summarize`, `walkthrough`, `backlog`, `full-report`와 어떤 관계인지 note-first UX 기준으로 적는다.

완료 기준:

- `.review-bot.yaml`의 최소 scope와 precedence가 한 문서에서 명확하다.
- 구현 전에 product ambiguity가 남지 않는다.
- 이후 implementation slice를 한 commit 단위로 자를 수 있다.

### 3. `ask` Command Boundary Definition

상태: `active`

왜 지금 하나:

- `ask`는 retrieval, session boundary, provider latency/cost, answer safety가 한꺼번에 얽혀 있어
  바로 구현하면 scope가 커진다.
- note command로 넣을 수 있는 최소 contract를 먼저 정해야 한다.

이번 작업의 범위:

1. `ask`가 참조할 수 있는 context source 범위를 정한다.
2. session을 저장하지 않을지, 최소한으로 저장할지 경계를 정한다.
3. provider unavailable / timeout / empty evidence일 때 응답 정책을 정한다.
4. `summarize` / `walkthrough` 이후에 붙는 note-family command로서의 UX 목적을 정리한다.

완료 기준:

- `ask`를 즉시 구현 가능한 최소 단위로 나눌 수 있다.
- retrieval/session/provider risk가 문서에서 먼저 분리된다.
- “무엇을 답하지 않을지”가 명확하다.

### 4. Local Backend Retained Artifact Capture Prep

상태: `active`

왜 지금 하나:

- `BOT_OPENAI_BASE_URL` wiring과 provenance는 이미 들어갔지만,
  실제 local backend baseline capture는 아직 환경 준비 단계에서 멈춘다.
- live capture 전에 repo-local 성공 기준과 artifact naming을 더 분명히 해야 한다.

이번 작업의 범위:

1. local backend 실험에 필요한 env contract를 정리한다.
2. direct smoke, provider-quality, comparison artifact의 retained filename 규칙을 고정한다.
3. “capture 성공”과 “human review required”를 구분하는 기준을 적는다.
4. local backend artifact가 direct OpenAI artifact와 섞이지 않도록 provenance 표현을 고정한다.

완료 기준:

- local backend 환경이 준비되면 capture 절차가 바로 실행 가능하다.
- retained artifact 이름과 provenance가 혼동되지 않는다.
- 이후 실험 결과를 provider tuning 근거로 재사용할 수 있다.

## Prepare Deferred Work

아래 항목은 아직 deferred 자체를 시작하지 않고,
나중에 바로 착수할 수 있게 선행 조건만 먼저 닫는 작업이다.

### 5. Provider / Ranking / Density Tuning Readiness Packet

상태: `queued`

연결 문서:

- [Deferred Provider And Model Work](/home/et16/work/review_system/docs/deferred/provider_and_model_work.md:1)

지금 할 사전 작업:

1. direct OpenAI smoke 성공 판정 조건을 다시 한 줄로 고정한다.
2. comparison artifact human review 체크리스트를 준비한다.
3. quota/billing 정상 환경이 준비되면 어떤 순서로 재수집할지 실행 절차를 짧게 만든다.

이 사전 작업이 끝나면:

- OpenAI direct artifact 재수집과 ranking/density tuning을 바로 시작할 수 있다.

### 6. Manual Rule Editor Readiness Packet

상태: `queued`

연결 문서:

- [Deferred Rule Authoring And Editor Work](/home/et16/work/review_system/docs/deferred/rule_authoring_and_editor.md:1)

지금 할 사전 작업:

1. lifecycle CLI가 이미 다루는 write boundary와 editor가 다뤄야 할 새 surface를 분리한다.
2. authoring에서 자주 틀리는 metadata/validation failure를 수집해 editor scope 후보를 정리한다.
3. editor가 canonical YAML과 Git history를 절대 우회하지 않는 운영 원칙을 한 번 더 고정한다.

이 사전 작업이 끝나면:

- manual rule editor를 UI/preview/validate 단위로 잘라 시작할 수 있다.

### 7. Multi-SCM Expansion Readiness Packet

상태: `queued`

연결 문서:

- [Deferred Platform Expansion](/home/et16/work/review_system/docs/deferred/platform_expansion.md:1)

지금 할 사전 작업:

1. GitHub adapter가 GitLab adapter와 달라지는 schema / note / thread / status 차이를 표로 정리한다.
2. smoke 또는 replay fixture에 필요한 repository / token / permission 요구사항을 적는다.
3. `ReviewSystemAdapterV2`에서 adapter별 extension point를 어디까지 허용할지 먼저 정한다.

이 사전 작업이 끝나면:

- GitHub PR adapter 설계를 큰 재조사 없이 시작할 수 있다.

### 8. Auto-Fix Safety Packet

상태: `queued`

연결 문서:

- [Deferred Automation Work](/home/et16/work/review_system/docs/deferred/automation_work.md:1)

지금 할 사전 작업:

1. low-risk fix class 후보를 좁히는 기준을 적는다.
2. reviewer approval, audit log, rollback 경계를 한 문서에서 정리한다.
3. `auto_fix_lines`를 실제 patch application flow와 연결할지 판단 기준을 만든다.

이 사전 작업이 끝나면:

- `@review-bot apply`를 설계만 길게 하지 않고 safety-first slice로 시작할 수 있다.

## Watch

아래 영역은 현재 roadmap의 직접 구현 대상이 아니다.

- Provider runtime guardrails
- Smoke and evaluation hardening
- Organization rule extension canonicalization
- Roadmap automation blocked artifact retention
- Minimal rule lifecycle CLI

변경이 생기면 여기서 다시 `active`로 올린다.

## Suggested Next Step

현재 가장 자연스러운 다음 작업은 `1. Evidence Refresh Path For Targeted Rule Expansion`이다.

이유:

- 지금 automation이 멈추는 가장 직접적인 원인이 evidence refresh ambiguity다.
- 이 경로를 먼저 고정하면 `Targeted Rule Expansion`이 다시 실행 가능한 product-facing slice로 돌아온다.
- 동시에 blocked artifact 운영과 next-gap selection 기준도 함께 정리된다.

## Validation Baseline

문서/계약 작업:

```bash
bash -n ops/scripts/advance_roadmap_with_codex.sh
```

`review-bot` contract 변경:

```bash
cd review-bot && uv run pytest tests/test_review_runner.py -q
cd review-bot && uv run pytest tests/test_api_queue.py -q
```

`review-engine` rule / lifecycle contract 변경:

```bash
cd review-engine && uv run pytest tests/test_rule_runtime.py tests/test_rule_lifecycle_cli.py -q
```

local smoke와 direct provider validation은 해당 작업이 실제 runtime/adapter/provider 경로를 건드릴 때만 추가한다.
