# Roadmap

## Purpose

이 문서는 앞으로 해야 할 일만 관리한다.
현재 구현 상세는 [CURRENT_SYSTEM.md](/home/et16/work/review_system/docs/CURRENT_SYSTEM.md:1)에 두고,
로드맵에는 완료된 기반 요약과 남은 실행 단위만 남긴다.

마지막 코드 상태 점검일: `2026-04-24`

상태 표기:

- `active`: 바로 작업할 우선순위가 높고, 한 번에 묶을 수 있는 실행 단위가 있다.
- `partial`: 일부 코드 골격이나 테스트는 있으나 운영 완료 기준에는 못 미친다.
- `not_started`: 현재 코드에 구현이 없다.
- `watch`: 새 기능 개발 대상은 아니며 회귀 방지와 운영 관찰만 한다.

## Completed Foundation

아래 항목은 새 로드맵 작업이 아니라 유지/회귀 방지 대상으로 본다.

| Area | 완료된 기반 |
| --- | --- |
| Review-bot Phase A Trust Foundation | runner-level verify path, lifecycle event history, finding outcomes analytics |
| Multi-language core canonicalization | current seed corpus coverage, language/profile/context/dialect routing, provider C++ fixed prior 제거 |
| CUDA native capability expansion | pipeline async, thread block cluster, TMA, WGMMA rule/profile 축 |
| Smoke fixture baseline | lifecycle smoke, mixed-language, curated polyglot, CUDA targeted fixture |
| Wrong-language telemetry loop | provenance/cause/actionability 분리, smoke event와 detector backlog 분리 |
| Provider quality / comparison / density gate | packaged provider quality corpus, deterministic `stub` gate, OpenAI opt-in skip path, provider comparison CLI, fixture `density_contract` |
| Provider-direct smoke split | lifecycle fallback smoke와 direct OpenAI smoke를 별도 신호로 분리 |
| Provider runtime provenance persistence | `ReviewRun.provider_runtime`와 finding payload `provider_runtime` 저장 위치 고정 |

## Work Split

바로 할 일과 나중에 할 일을 아래처럼 나눈다.

### Do Now

- external API quota나 별도 권한 없이 닫을 수 있는 작업만 잡는다.
- 한 commit에서 source/rule/detector/example/validation까지 닫히는 단위를 우선한다.
- deterministic release gate로 먼저 검증 가능한 작업을 우선한다.

### Do Later

아래 항목은 blocker, 선행 조건, 작업 성격에 따라 별도 문서로 분리한다.

- [Deferred Provider And Model Work](/home/et16/work/review_system/docs/deferred/provider_and_model_work.md:1)
- [Deferred Rule Authoring And Editor Work](/home/et16/work/review_system/docs/deferred/rule_authoring_and_editor.md:1)
- [Deferred Platform Expansion](/home/et16/work/review_system/docs/deferred/platform_expansion.md:1)
- [Deferred Automation Work](/home/et16/work/review_system/docs/deferred/automation_work.md:1)

## Now

### 1. Provider Runtime Guardrails

상태: `watch`

최근 완료:

- `GET /internal/review/requests/{review_system}/{project_ref}/{review_request_id}` current-state API가
  마지막 run의 `provider_runtime`(configured/effective provider, fallback 여부/사유)를 직접 반환한다.
- `BOT_PROVIDER`, `BOT_FALLBACK_PROVIDER`를 `openai`/`stub` allowlist로 검증하고,
  unsupported 값은 settings/provider factory에서 startup fail-fast 한다.
- PR summary general note와 publish structured log가
  `provider_runtime_summary`를 함께 노출해 live provider path와 stub fallback path를 바로 읽을 수 있다.
- `ops/scripts/smoke_openai_provider_direct.sh`가 스크립트 위치 기준으로 repo root를 기본 해석하고,
  `REVIEW_SYSTEM_ROOT`, `REVIEW_SYSTEM_ENV_FILE` override와 resolved root/env provenance 출력을 지원한다.
- `review-bot/tests/test_openai_provider_direct_smoke.py`가
  relocated root와 explicit env override contract를 network stub으로 고정한다.

검증 메모:

- 이번 slice는 direct smoke script의 root/env loading contract만 바꿨으므로
  `uv run --project review-bot pytest review-bot/tests/test_openai_provider_direct_smoke.py -q`와
  `bash -n ops/scripts/smoke_openai_provider_direct.sh`만 다시 돌린다.
- deterministic validation은 live direct OpenAI나 lifecycle stub fallback을 쓰지 않고
  script-level network stub만 사용한다.
- local GitLab lifecycle smoke와 live direct OpenAI smoke는 건너뛴다.

남은 구현 작업:

- 없음

### 2. Smoke And Evaluation Hardening

상태: `watch`

운영 원칙:

- `release gate`와 `pre-release smoke`는 이미 분리됐다.
- wrong-language telemetry/backlog snapshot은 정기 checkpoint로만 관찰한다.

남은 구현 작업:

- 없음

### 3. Targeted Rule Expansion

상태: `partial`

최근 완료:

- `GO.13`이 direct chained `json.NewDecoder(...).Decode(...)`뿐 아니라
  `decoder := json.NewDecoder(...)` 뒤 `decoder.Decode(...)` 경로까지 잡도록 넓어졌다.
- `GO.13` bundled code/diff example과 safe regression이 retained decoder shape를 포함하도록 갱신됐다.
- 이번 slice의 deterministic release gate는 `review-engine` ingest/examples/diff contracts만 다시 돌렸고,
  `review-bot`/`review-platform`, GitLab lifecycle smoke, mixed-language smoke, direct OpenAI/provider validation은 범위 밖으로 유지했다.

최근에 정리된 gap:

- `DOCKER.SEC.7` build-time secret handling
- `DOCKER.3` digestless base tag retrieval hardening
- `DOCKER.7` runtime prefix copy rule
- `GO.11` sentinel error matching
- `GO.12` transaction rollback visibility
- `GO.13` net/http handler framework binding follow-up

다음 작업:

1. telemetry나 smoke에서 남아 있는 under-trigger gap 하나를 고른다.
2. source atom 또는 source 문서, detector/rule/example을 같은 단위에서 갱신한다.
3. `review-engine`만 바뀌면 rule/retrieval baseline만 다시 돌리고, `review-bot`이나 lifecycle 영향이 생기면 그에 맞는 regression과 smoke 범위를 추가한다.
4. 같은 Go handler family에서 under-trigger가 남아 있으면 framework binding path를 별도 slice로 넓힐지 결정한다.

검증 메모:

- 이번 slice는 `review-engine` source/rule/detector/example만 변경했다.
- rerun:
  - `uv run --project review-engine python -m review_engine.cli.ingest_guidelines`
  - `uv run --project review-engine python -m review_engine.cli.evaluate_examples`
  - `uv run --project review-engine python -m review_engine.cli.evaluate_diff_contracts`
- `review-bot`/`review-platform` tests, GitLab lifecycle smoke, mixed-language smoke, direct OpenAI/provider validation은 이번 범위 밖이라 생략했다.

현재 1순위 후보:

- Go: HTTP handler boundary validation framework binding follow-up

완료 기준:

- source, coverage, rule/policy, detector, regression, ingest 검증이 한 번에 들어간다.
- rule 추가가 provider/ranking/density baseline을 악화시키지 않는다.

### 4. Review-Bot Context And UX

상태: `partial`

다음 작업:

1. hunk 기반 review unit split의 한계를 측정하고 syntax-aware split이 필요한 언어를 고른다.
2. related file retrieval과 project-scoped codebase index를 분리 설계한다.
3. `full-report`/`backlog` note에 “왜 이 항목이 보였는가” 설명을 작게 추가한다.
4. project-local feedback이 global quality metric을 왜곡하지 않도록 learned weight granularity를 정한다.
5. `.review-bot.yaml`, `summarize`, `ask`, walkthrough note의 우선순위를 재평가한다.

완료 기준:

- backlog와 surfacing reason이 사용자에게 더 잘 설명된다.
- project-local feedback이 global quality metric을 왜곡하지 않는다.
- context retrieval이 false-positive를 줄이는지 deterministic fixture로 확인된다.

### 5. Organization Rule Extension

상태: `partial`

다음 작업:

1. 실제 private extension 샘플 root를 하나 만든다.
2. CI에서 public-only와 private-enabled 경로를 분리한다.
3. extension failure policy를 dev/prod별로 문서화하고 설정 예제를 추가한다.
4. `source_family` legacy alias 제거 또는 장기 호환 방침을 결정한다.
5. `pack_weight`, `reference_only`, conflict action의 운영 표현 방식을 확정한다.

완료 기준:

- public core는 private extension 없이 항상 동작한다.
- private extension은 명시 설정으로만 로드된다.
- private rule priority가 retrieval/rerank/prompt/detector에서 일관된다.
- public/private 경계가 깨지면 CI에서 잡힌다.

## Suggested Next Step

현재 가장 자연스러운 다음 작업은 `Targeted Rule Expansion`의
Go HTTP handler boundary validation에서 framework binding path를 별도 slice로 넓힐지 판단하는 것이다.

이유:

- `Provider Runtime Guardrails`는 watch 상태로 내려갔고 남은 실행 단위가 없다.
- `Targeted Rule Expansion`은 여전히 source/rule/detector/example/validation을 한 번에 닫을 수 있는
  가장 작은 product-facing 실행 단위를 유지하고 있다.
- `GO.13`이 direct chained decode와 retained decoder variable path를 모두 닫았으므로,
  다음에는 framework binding을 같은 family의 다음 slice로 볼지 아니면 다른 under-trigger gap으로 넘어갈지를 telemetry 기준으로 바로 결정할 수 있다.

## Queued After Main Roadmap

main `ROADMAP.md`의 현재 항목을 다 돌린 뒤 곧바로 이어서 할 후보는 아래 순서로 관리한다.

### 6. Roadmap Automation Audit Artifact

상태: `not_started`

다음 작업:

1. blocked unit / reason / attempt / date를 어떤 형식으로 남길지 정한다.
2. `advance_roadmap_with_codex.sh`가 영속 artifact를 남기게 만든다.
3. repeated blocker를 집계할 최소 운영 절차를 문서화한다.

완료 기준:

- blocked skip 결과가 임시 파일이 아니라 repo-local artifact로 남는다.
- 반복 blocker를 roadmap prioritization 입력으로 재사용할 수 있다.

### 7. Minimal Rule Lifecycle CLI

상태: `not_started`

범위:

- `list`
- `show`
- `disable`
- `enable`

다음 작업:

1. 최소 lifecycle CLI의 입력/출력과 canonical YAML 경계를 정한다.
2. rule 변경 후 validate/ingest/test 연결 방식을 명령 단위로 묶는다.
3. full editor/UI 없이도 운영에 도움이 되는 작은 관리 흐름부터 닫는다.

완료 기준:

- 최소 CLI만으로 rule 조회와 on/off 관리가 가능하다.
- generated artifact와 canonical source 경계가 흐려지지 않는다.

### 8. OpenAI-Compatible Local LLM Backend

상태: `not_started`

다음 작업:

1. OpenAI-compatible endpoint 전략을 고른다.
2. fallback 정책과 structured output 품질 기준을 정한다.
3. local backend smoke와 provider quality baseline 범위를 정한다.

완료 기준:

- OpenAI API와 분리된 local backend 실험 경로가 생긴다.
- live provider / local provider / stub fallback을 비교 가능한 구조로 확장할 수 있다.

## Not Now

지금 당장 잡지 않는 대표 항목은 아래와 같다.

- provider / ranking / density direct tuning
  - 이유: direct OpenAI path가 현재 `insufficient_quota`로 막혀 있다.
- manual rule editor / authoring UX
  - 이유: 현재는 YAML/Git 기반 수동 편집 토대는 있지만 editor/UI와 lifecycle CLI를 바로 넣을 시점은 아니다.
- multi-SCM adapter expansion
  - 이유: GitHub/Gerrit adapter는 설계/fixture/smoke까지 한 단위가 커서 현재 우선순위보다 뒤다.
- review-bot apply / auto-fix automation
  - 이유: trust metric, low-risk fix class, audit/rollback 경계가 선행 조건이다.

## Validation Baseline

`release gate`:

- network 없이 재현 가능한 deterministic 검증이다.
- 일반 PR 확인이나 기본 CI 후보는 이 범주를 기본으로 사용한다.

일반 변경:

```bash
uv run --project review-engine pytest review-engine/tests -q
uv run --project review-bot pytest review-bot/tests -q
uv run --project review-platform pytest review-platform/tests/test_pr_flow.py -q
```

Rule/retrieval 변경:

```bash
uv run --project review-engine python -m review_engine.cli.ingest_guidelines
uv run --project review-engine python -m review_engine.cli.evaluate_examples
uv run --project review-engine python -m review_engine.cli.evaluate_diff_contracts
```

Provider/ranking/density 변경:

```bash
uv run --project review-bot pytest review-bot/tests/test_multilang_smoke_fixture.py review-bot/tests/test_provider_quality.py -q
uv run --project review-bot python -m review_bot.cli.evaluate_provider_quality \
  --provider stub \
  --json-output /tmp/provider_quality_stub.json
```

`pre-release smoke`:

- local GitLab 상태, webhook, replay fixture가 준비된 환경에서만 돌린다.
- adapter/lifecycle/routing 변경이나 배포 전 확인에 사용한다.

GitLab/lifecycle 변경:

```bash
bash ops/scripts/smoke_local_gitlab_lifecycle_review.sh
```

Multilanguage/routing 변경:

```bash
bash ops/scripts/smoke_local_gitlab_multilang_review.sh --fixture synthetic-mixed-language
bash ops/scripts/smoke_local_gitlab_multilang_review.sh --fixture curated-polyglot --project-ref root/review-system-curated-polyglot-smoke
bash ops/scripts/smoke_local_gitlab_multilang_review.sh --fixture cuda-targeted --project-ref root/review-system-cuda-smoke
```

direct provider / comparison artifact:

- deterministic release gate와 별개로 본다.
- `evaluate_provider_quality --provider openai`는 `OPENAI_API_KEY`가 없으면 `skipped` artifact를 남기고 성공 종료할 수 있다.
- fallback이 켜져 있으면 lifecycle smoke만으로 live OpenAI direct 성공을 증명할 수 없다.

```bash
uv run --project review-bot python -m review_bot.cli.evaluate_provider_quality \
  --provider openai \
  --json-output /tmp/provider_quality_openai.json
uv run --project review-bot python -m review_bot.cli.compare_provider_quality \
  --stub-json /tmp/provider_quality_stub.json \
  --openai-json /tmp/provider_quality_openai.json
```
