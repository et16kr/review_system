# Review Roadmap

## Purpose

이 문서는 `gpt-5.5`로 현재 저장소를 처음부터 다시 리뷰하기 위한 전용 roadmap이다.
구현 roadmap과 분리해, 시스템 방향성, 버그 위험, 과도한 기능, 부족한 기능,
인터페이스 개선 가능성, 문서/코드 불일치를 단계별로 점검한다.

이번 리뷰 라운드는 이전 `gpt-5.4` 리뷰 결과를 이어받지 않고 새로 시작한다.
이전 결과는 git history에 남아 있으며, 현재 누적 결과 문서는 새 라운드 기준으로 다시 채운다.

마지막 코드 상태 점검일: `2026-04-24`

상태 표기:

- `active`: 지금 바로 리뷰 단위로 실행 가능하다.
- `queued`: 앞선 리뷰 결과가 모이면 바로 이어서 할 수 있다.
- `watch`: 이번 리뷰 라운드에서는 새 작업이 없다.

## Model And Execution

권장 실행:

```bash
ops/scripts/advance_review_roadmap_with_codex.sh --model gpt-5.5 --max-iters 1
```

전체 라운드를 자동으로 진행할 때:

```bash
ops/scripts/advance_review_roadmap_with_codex.sh --model gpt-5.5 --until-done
```

원칙:

- 한 review unit은 반드시 [CURRENT_STATE_REVIEW.md](/home/et16/work/review_system/docs/reviews/CURRENT_STATE_REVIEW.md:1) 또는 [REVIEW_FINDINGS_BACKLOG.md](/home/et16/work/review_system/docs/reviews/REVIEW_FINDINGS_BACKLOG.md:1)를 갱신한다.
- 리뷰 unit은 기본적으로 코드 수정을 하지 않는다.
- 명확한 typo나 문서 링크 오류처럼 리뷰 진행 자체를 방해하는 수정만 같은 unit에서 허용한다.
- findings는 반드시 evidence, impact, recommended action을 포함한다.
- local smoke, direct provider, OpenAI API 검증은 해당 unit이 그 신호를 실제 근거로 필요로 할 때만 실행한다.
- validation fail/hang은 자동 blocker가 아니다. 정적 근거와 부분 검증으로 판단이 가능하면
  evidence limitation으로 기록하고 다음 review unit으로 진행한다.

## Review Questions

이번 라운드는 아래 질문을 끝까지 추적한다.

- 이 리뷰 봇 프로그램의 방향성은 현재도 맞는가?
- 실제 버그, race, stale contract, regression 위험은 없는가?
- 필요 없는데 남아 있는 기능, wrapper, compatibility path, 문서가 있는가?
- 부족한 기능이나 안전장치가 있는데 roadmap에 빠져 있지는 않은가?
- 사용자가 보는 인터페이스와 운영자가 보는 인터페이스를 더 단순하게 만들 수 있는가?
- 테스트와 smoke는 실제 gate 역할을 하는가, 아니면 통과 신호가 약한가?
- deferred 항목은 정말 미루는 게 맞는가, 아니면 지금 준비 작업이 필요한가?

## Review Outputs

- [docs/reviews/CURRENT_STATE_REVIEW.md](/home/et16/work/review_system/docs/reviews/CURRENT_STATE_REVIEW.md:1)
  - findings-first 현재 상태 리뷰 본문
- [docs/reviews/REVIEW_FINDINGS_BACKLOG.md](/home/et16/work/review_system/docs/reviews/REVIEW_FINDINGS_BACKLOG.md:1)
  - 후속 작업 후보, severity, area, recommended action 정리

## Post-Review Handoff

리뷰가 끝난 뒤에는 결과를 아래 세 작업으로 나눈다.

1. 리뷰에서 찾은 버그 수정
2. 리뷰 결과를 바탕으로 [ROADMAP.md](/home/et16/work/review_system/docs/ROADMAP.md:1) 수정
3. 리뷰 결과를 바탕으로 `docs/deferred/*.md` 수정

따라서 모든 finding과 backlog entry는 아래 중 하나로 분류해야 한다.

- `bug_fix`: 코드나 테스트를 직접 고쳐야 한다.
- `roadmap_update`: 지금 바로 할 일로 승격하거나 `ROADMAP.md`를 보정해야 한다.
- `deferred_update`: 장기 작업, 선행 조건, 미룰 이유를 deferred 문서에 반영해야 한다.
- `remove`: 필요 없거나 혼란을 주는 기능, wrapper, 문서를 제거해야 한다.
- `keep`: 현재 방향이 적절하므로 유지 근거만 남긴다.
- `needs_decision`: 제품/운영 결정이 먼저 필요하다.

## Now

### 1. Review Frame And Evidence Reset

상태: `watch`

완료: `2026-04-24`

이번 작업의 범위:

1. 새 `gpt-5.5` 리뷰 라운드의 scope, evidence source, finding format을 고정한다.
2. 이전 라운드 findings와 이번 라운드 findings가 섞이지 않도록 결과 문서의 라운드 기준을 명확히 한다.
3. 어떤 검증은 정적 읽기로 충분하고 어떤 검증은 실행이 필요한지 분리한다.
4. `REVIEW_FINDINGS_BACKLOG.md`의 intake rule을 새 라운드 기준으로 고정한다.

완료 기준:

- 새 리뷰 라운드의 산출물 형식이 정해진다.
- 이후 unit이 같은 형식으로 누적 기록할 수 있다.

완료 기록:

- [CURRENT_STATE_REVIEW.md](/home/et16/work/review_system/docs/reviews/CURRENT_STATE_REVIEW.md:1)에
  evidence level, validation policy, finding format을 고정했다.
- [REVIEW_FINDINGS_BACKLOG.md](/home/et16/work/review_system/docs/reviews/REVIEW_FINDINGS_BACKLOG.md:1)에
  actionable finding만 intake하는 rule을 고정했다.
- 검증은 `git diff --check`로 제한했다. local GitLab smoke와 OpenAI direct smoke는
  이 문서-only unit의 근거로 필요하지 않아 실행하지 않았다.

### 2. Product Direction And Scope Review

상태: `watch`

완료: `2026-04-24`

이번 작업의 범위:

1. README, CURRENT_SYSTEM, API_CONTRACTS, ROADMAP, deferred 문서를 읽고 제품 방향성을 재평가한다.
2. `review-engine`, `review-bot`, `review-platform`, `ops`의 책임 분리가 지금도 적절한지 본다.
3. 지금 프로그램이 “코드리뷰 봇”으로서 집중해야 할 핵심 가치와 벗어난 기능을 구분한다.
4. roadmap에 있는 일과 실제 사용자 가치가 맞는지 검토한다.

완료 기준:

- 방향성을 유지할지, 줄일지, 더 투자할지에 대한 1차 결론이 문서에 남는다.
- 필요 없거나 과한 기능 후보가 backlog에 들어간다.

완료 기록:

- [CURRENT_STATE_REVIEW.md](/home/et16/work/review_system/docs/reviews/CURRENT_STATE_REVIEW.md:1)에
  제품 방향성 1차 결론을 남겼다. 현재 방향은 유지하되, 넓은 surface는 contract-first
  또는 deferred/readiness packet 상태로 두는 것이 맞다고 평가했다.
- 새 actionable backlog entry는 만들지 않았다. 과한 기능 후보로 볼 수 있는
  `ask`, `.review-bot.yaml`, provider tuning, multi-SCM, auto-fix, manual editor는
  이미 implementation roadmap 또는 deferred 문서에서 선행 조건과 함께 분리되어 있다.
- 검증은 `git diff --check`로 제한했다. local GitLab smoke와 OpenAI direct smoke는
  이 문서-only product review의 근거로 필요하지 않아 실행하지 않았다.

### 3. Architecture And Boundary Review

상태: `watch`

완료: `2026-04-24`

이번 작업의 범위:

1. canonical `ReviewRequestKey` 경계와 실제 코드 사용처가 일치하는지 점검한다.
2. `review-platform`이 local harness인지, 실제 product boundary처럼 남아 있는지 확인한다.
3. adapter, runner, API, DB schema, lifecycle event 경계가 과하게 섞이지 않았는지 본다.
4. 오래된 compatibility path와 current contract의 충돌을 찾는다.

완료 기준:

- architecture-level bug risk와 cleanup 후보가 findings로 남는다.
- 다음 구현 roadmap에 넣어야 할 경계 정리 작업이 선별된다.

완료 기록:

- [CURRENT_STATE_REVIEW.md](/home/et16/work/review_system/docs/reviews/CURRENT_STATE_REVIEW.md:1)에
  architecture boundary review 결과를 남겼다. canonical `ReviewRequestKey`는 문서,
  API, DB, runner lookup, GitLab adapter 경계에서 일관된 것으로 평가했다.
- [REVIEW_FINDINGS_BACKLOG.md](/home/et16/work/review_system/docs/reviews/REVIEW_FINDINGS_BACKLOG.md:1)에
  local harness BotClient가 제거된 legacy `pr_id` bot endpoint를 호출하는 문제를
  후속 direct fix 후보로 추가했다.
- 검증은 `git diff --check`로 제한했다. 이 static architecture review는 local GitLab
  smoke나 OpenAI direct smoke의 runtime signal을 근거로 삼지 않았다.

### 4. `review-engine` Correctness Review

상태: `watch`

완료: `2026-04-24`

이번 작업의 범위:

1. rule source, profile, policy, pack identity, source family alias 경계를 검토한다.
2. ingest, retrieval, rerank, detector, source coverage matrix가 서로 일관되는지 본다.
3. 최근 rule expansion이 source/rule/detector/example/validation 묶음을 실제로 지키는지 확인한다.
4. duplicate identity, silent override, stale generated artifact 같은 위험을 찾는다.

완료 기준:

- engine correctness 관련 bugs 또는 regression risks가 정리된다.
- rule expansion과 authoring boundary의 현재 방향성 평가가 남는다.

완료 기록:

- [CURRENT_STATE_REVIEW.md](/home/et16/work/review_system/docs/reviews/CURRENT_STATE_REVIEW.md:1)에
  engine correctness review 결과를 남겼다. 현재 canonical YAML, generated dataset,
  runtime retrieval selection은 번들 상태에서 일치한다고 평가했다.
- [REVIEW_FINDINGS_BACKLOG.md](/home/et16/work/review_system/docs/reviews/REVIEW_FINDINGS_BACKLOG.md:1)에
  unresolved/duplicate selected pack fail-fast, default profile config 정리, canonical rule
  reverse coverage validation을 후속 direct fix 후보로 추가했다.
- 검증은 `git diff --check`로 제한했다. 이 static `review-engine` correctness review는
  local GitLab smoke나 OpenAI direct smoke의 runtime signal을 근거로 삼지 않았다.

### 5. `review-engine` Authoring And Lifecycle UX Review

상태: `watch`

완료: `2026-04-24`

이번 작업의 범위:

1. minimal rule lifecycle CLI가 실제 운영자 UX로 충분한지 검토한다.
2. manual rule editor deferred 판단이 여전히 맞는지 재검토한다.
3. authoring validation failure가 충분히 설명되는지 본다.
4. 필요 없거나 너무 넓어진 authoring surface를 찾는다.

완료 기준:

- CLI 유지, editor deferred, 추가 authoring guardrail 여부가 정리된다.
- rule authoring 개선 후보가 backlog에 들어간다.

완료 기록:

- [CURRENT_STATE_REVIEW.md](/home/et16/work/review_system/docs/reviews/CURRENT_STATE_REVIEW.md:1)에
  rule lifecycle CLI는 narrow canonical YAML mutation surface로 유지하는 것이 맞고,
  manual editor는 strict schema/readiness packet 전까지 deferred가 맞다는 판단을 남겼다.
- [REVIEW_FINDINGS_BACKLOG.md](/home/et16/work/review_system/docs/reviews/REVIEW_FINDINGS_BACKLOG.md:1)에
  canonical YAML authoring model이 unknown key를 silent ignore하는 문제를 후속 direct fix
  후보로 추가했다.
- 검증은 `git diff --check`와
  `cd review-engine && UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_rule_runtime.py tests/test_rule_lifecycle_cli.py -q`로
  제한했다. local GitLab smoke와 OpenAI direct smoke는 이 static `review-engine`
  authoring UX review의 근거로 필요하지 않아 실행하지 않았다.

### 6. `review-bot` Lifecycle Correctness Review

상태: `watch`

완료: `2026-04-24`

이번 작업의 범위:

1. detect, publish, sync, verify 흐름을 다시 점검한다.
2. run state, finding lifecycle event, feedback analytics가 source of truth를 혼동하지 않는지 본다.
3. GitLab note trigger, queue handoff, stale head handling, thread sync risk를 찾는다.
4. lifecycle 코드가 adapter-specific detail을 과하게 품고 있지 않은지 확인한다.

완료 기준:

- lifecycle bug risk와 missing tests가 findings로 남는다.
- smoke가 필요한 부분과 deterministic test로 충분한 부분이 분리된다.

완료 기록:

- [CURRENT_STATE_REVIEW.md](/home/et16/work/review_system/docs/reviews/CURRENT_STATE_REVIEW.md:1)에
  `review-bot` lifecycle boundary review 결과를 남겼다. Runner-owned detect -> publish ->
  sync boundary와 immutable lifecycle event 방향은 유지하되, GitLab note-trigger expected
  head가 끝까지 settle되지 않을 때 stale diff로 성공할 수 있는 위험을 확인했다.
- [REVIEW_FINDINGS_BACKLOG.md](/home/et16/work/review_system/docs/reviews/REVIEW_FINDINGS_BACKLOG.md:1)에
  never-settled expected head fail/defer 처리와 adapter thread/feedback identity scope 정리를
  후속 direct fix 후보로 추가했다.
- 검증은 제한적으로 완료했다. Runner-only lifecycle subset
  `timeout 180s .venv/bin/pytest ...test_review_runner... -q`는 `5 passed`로 성공했지만,
  `cd review-bot && UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_review_runner.py tests/test_api_queue.py -q`가
  partial progress 이후 hang 되었고, 단일 API queue webhook test도
  `starlette.testclient.TestClient.__enter__`에서 timeout 되었다. 이 hang은 review 판단의
  필수 근거가 아니라 validation limitation과 후속 test-gate 조사 대상으로 남긴다.
- local GitLab smoke는 runtime webhook/thread evidence가 필요하지 않아 실행하지 않았다.
  OpenAI direct smoke는 configuration에 의해 skipped였고, provider signal은 deterministic
  fake/stub provider path만 사용했다.

### 7. Provider, Fallback, And Model Backend Review

상태: `watch`

완료: `2026-04-24`

이번 작업의 범위:

1. OpenAI direct path, local OpenAI-compatible base URL, stub fallback 경계를 점검한다.
2. lifecycle smoke 통과와 direct provider 성공이 실제로 분리되어 보이는지 본다.
3. provider runtime provenance가 API, log, note, artifact에 충분히 드러나는지 확인한다.
4. `OPENAI_API_KEY` quota 문제처럼 외부 blocker가 자동화와 문서에 제대로 표현되는지 본다.

완료 기준:

- provider signal 혼동, fail-open/fail-fast 경계, local LLM 준비 상태가 정리된다.
- missing guardrail이나 불필요한 provider surface가 backlog에 들어간다.

완료 기록:

- [CURRENT_STATE_REVIEW.md](/home/et16/work/review_system/docs/reviews/CURRENT_STATE_REVIEW.md:1)에
  provider/fallback boundary review 결과를 남겼다. Lifecycle smoke, direct provider smoke,
  provider quality artifact는 별도 signal로 유지하는 현재 방향이 맞다고 평가했다.
- [REVIEW_FINDINGS_BACKLOG.md](/home/et16/work/review_system/docs/reviews/REVIEW_FINDINGS_BACKLOG.md:1)에
  lifecycle `provider_runtime`이 OpenAI-compatible local backend의 model/base URL/transport
  provenance를 API, log, summary note에 충분히 드러내지 못하는 문제를 후속 direct fix
  후보로 추가했다.
- 검증은 deterministic provider path로 제한했다. Targeted provider tests는 `15 passed`,
  `stub` provider quality는 `6 passed`, OpenAI provider quality/comparison은
  `OPENAI_API_KEY` 없이 `skipped` artifact와 runtime provenance를 남겼다.
- OpenAI direct smoke는 configuration에 의해 skipped였으므로 live OpenAI 성공 주장을 하지
  않았다. local GitLab smoke는 provider boundary 판단에 필요하지 않아 실행하지 않았다.

### 8. User Interface And Review UX Review

상태: `watch`

완료: `2026-04-24`

이번 작업의 범위:

1. `review`, `full-report`, `backlog`, `help`, `summarize`, `walkthrough` command UX를 점검한다.
2. `.review-bot.yaml`과 `ask`가 지금 필요한지, 아니면 더 미뤄야 하는지 판단한다.
3. general note, inline comment, backlog note가 사용자에게 충분히 설명적인지 본다.
4. 너무 많은 command나 note surface가 생겨 혼란을 만들지 않는지 확인한다.

완료 기준:

- 사용자-facing interface 개선 후보가 정리된다.
- 빼거나 미룰 command surface와 추가할 safety copy가 구분된다.

완료 기록:

- [CURRENT_STATE_REVIEW.md](/home/et16/work/review_system/docs/reviews/CURRENT_STATE_REVIEW.md:1)에
  user-facing command와 note UX review 결과를 남겼다. 현재 6개 command surface와
  summarize -> backlog -> full-report reading path는 유지하고, `.review-bot.yaml`과 `ask`는
  contract-definition work 전까지 구현하지 않는 판단이 맞다고 평가했다.
- [REVIEW_FINDINGS_BACKLOG.md](/home/et16/work/review_system/docs/reviews/REVIEW_FINDINGS_BACKLOG.md:1)에
  directed unknown command가 webhook response에서만 ignored_reason을 반환해 GitLab 사용자에게
  visible feedback을 주지 않는 문제를 후속 direct fix 후보로 추가했다.
- 검증은 targeted deterministic UX tests로 제한했다. Command parser와 note renderer subset은
  `11 passed`로 성공했다. local GitLab smoke는 runtime webhook/thread evidence가 필요하지
  않아 실행하지 않았다. OpenAI direct smoke는 configuration에 의해 skipped였고, provider
  validation은 이 UX review의 근거로 사용하지 않았다.

### 9. Ops, Smoke, And Automation Review

상태: `watch`

완료: `2026-04-24`

이번 작업의 범위:

1. local GitLab lifecycle smoke, multilang smoke, provider-direct smoke, roadmap automation의 신뢰 경계를 검토한다.
2. 통과 신호가 약한 smoke와 release gate로 쓸 수 있는 deterministic validation을 분리한다.
3. blocked artifact, skip policy, `--until-done`, `--roadmap-file`, review wrapper가 실제 운영에 충분한지 본다.
4. 중복 wrapper, 오래된 script name, 환경 의존성이 과도한 부분을 찾는다.

완료 기준:

- ops/automation cleanup 후보와 safety 개선 후보가 backlog에 들어간다.
- review automation 자체의 사용법과 한계가 명확해진다.

완료 기록:

- [CURRENT_STATE_REVIEW.md](/home/et16/work/review_system/docs/reviews/CURRENT_STATE_REVIEW.md:1)에
  ops smoke와 roadmap automation review 결과를 남겼다. Release gate, local GitLab
  pre-release smoke, direct provider smoke를 분리하는 현재 운영 경계는 유지하는 것이 맞다고
  평가했다.
- [REVIEW_FINDINGS_BACKLOG.md](/home/et16/work/review_system/docs/reviews/REVIEW_FINDINGS_BACKLOG.md:1)에
  review-roadmap blocked unit artifact retention과 OpenAI direct smoke preflight timeout을
  후속 direct fix 후보로 추가했다.
- 검증은 static/deterministic scope로 제한했다. Shell syntax, Python compile, direct-smoke
  fake-curl tests, multilang fixture contract tests, wrong-language baseline rendering tests가
  통과했다. local GitLab lifecycle/multilang smoke는 runtime evidence가 필수 근거가 아니어서
  실행하지 않았다. OpenAI direct smoke는 configuration에 의해 skipped였고 live OpenAI 성공
  판단은 하지 않았다.

### 10. Docs, Roadmap, And Deferred Review

상태: `watch`

완료: `2026-04-24`

이번 작업의 범위:

1. `ROADMAP.md`, `REVIEW_ROADMAP.md`, deferred 문서들이 서로 역할을 잘 나누는지 본다.
2. roadmap에 빠진 부족한 작업이 있는지 찾는다.
3. deferred에 남긴 항목이 정말 deferred인지, 지금 사전 작업이 필요한지 판단한다.
4. 문서가 실제 코드보다 앞서가거나 뒤처진 곳을 찾는다.

완료 기준:

- roadmap/deferred 재배치 제안이 정리된다.
- 빠진 개선 항목이 있으면 backlog에 들어간다.

완료 기록:

- [CURRENT_STATE_REVIEW.md](/home/et16/work/review_system/docs/reviews/CURRENT_STATE_REVIEW.md:1)에
  roadmap/deferred 역할 분리 review 결과를 남겼다. Active roadmap은 evidence refresh,
  note-first UX contract, local backend artifact prep, deferred readiness packet으로 제한되어
  있어 큰 방향은 유지하는 것이 맞다고 평가했다.
- [REVIEW_FINDINGS_BACKLOG.md](/home/et16/work/review_system/docs/reviews/REVIEW_FINDINGS_BACKLOG.md:1)에
  broad watch label 보정과 private rule packaging owner 추가를 post-review
  `docs/ROADMAP.md` update 후보로 추가했다.
- 검증은 static docs/code review와 `git diff --check`로 제한했다. local GitLab smoke와
  OpenAI direct smoke는 이 docs/roadmap/deferred review의 runtime signal로 필요하지 않아
  실행하지 않았다.

### 11. Dead Code, Dead Docs, And Cleanup Review

상태: `watch`

완료: `2026-04-24`

이번 작업의 범위:

1. 더 이상 쓰이지 않는 wrapper, config, test fixture, compatibility path를 찾는다.
2. 이름 때문에 혼란을 주는 파일이나 문서를 찾는다.
3. 삭제 가능한 것과 compatibility 때문에 유지해야 하는 것을 구분한다.

완료 기준:

- cleanup 후보가 risk와 함께 backlog에 정리된다.

완료 기록:

- [CURRENT_STATE_REVIEW.md](/home/et16/work/review_system/docs/reviews/CURRENT_STATE_REVIEW.md:1)에
  dead code/docs cleanup review 결과를 남겼다. Tracked generated/cache artifact는 발견하지
  않았고, root `ROADMAP_AUTOMATION_DESIGN.md`도 남아 있지 않았다.
- [REVIEW_FINDINGS_BACKLOG.md](/home/et16/work/review_system/docs/reviews/REVIEW_FINDINGS_BACKLOG.md:1)에
  unowned `review-engine/app/` Next.js scaffold, orphan root `review_system.md`, local GitLab
  smoke의 TDE-named primary surface를 cleanup 후보로 추가했다.
- 검증은 static scan, `bash -n`, `python3 -m py_compile`, `git diff --check`로 제한했다.
  첫 broad `rg`는 local GitLab runtime volume인 `ops/gitlab/**` permission 때문에 실패했지만,
  같은 scan을 해당 runtime data directory 제외 후 통과시켰다. local GitLab smoke와 OpenAI
  direct smoke는 이 cleanup review의 runtime signal로 필요하지 않아 실행하지 않았다.

## Queue

### 12. Test Coverage And Missing Gate Review

상태: `active`

이번 작업의 범위:

1. findings에서 반복적으로 나온 위험이 테스트로 막혀 있는지 확인한다.
2. missing deterministic test와 missing smoke를 구분한다.
3. 테스트가 너무 넓거나 느려서 gate 역할을 못 하는 곳을 찾는다.

완료 기준:

- 추가해야 할 targeted test, 줄여도 되는 smoke, 유지해야 할 release gate가 정리된다.

### 13. Consolidated Review Outcome

상태: `queued`

이번 작업의 범위:

1. 누적 findings를 severity와 실행 가능성 기준으로 다시 정렬한다.
2. 즉시 수정할 것, 구현 roadmap에 넣을 것, deferred에 둘 것을 최종 분류한다.
3. `REVIEW_FINDINGS_BACKLOG.md`를 후속 실행용 backlog로 정리한다.
4. 필요하면 `ROADMAP.md`와 deferred 문서에 반영할 제안 목록을 만든다.
5. post-review handoff를 `bug_fix`, `roadmap_update`, `deferred_update`, `remove`, `keep`, `needs_decision`으로 나눠 최종 정리한다.

완료 기준:

- 이번 `gpt-5.5` 리뷰 라운드의 최종 결론과 다음 실행 목록이 한눈에 보인다.
- 이후 버그 수정, `ROADMAP.md` 수정, deferred 문서 수정 작업을 별도 판단 없이 시작할 수 있다.

## Suggested Next Step

현재 다음 실행 단위는 `12. Test Coverage And Missing Gate Review`다.

이유:

- `1. Review Frame And Evidence Reset`에서 새 라운드의 evidence, validation, finding,
  backlog intake contract를 고정했다.
- `2. Product Direction And Scope Review`에서 현재 제품 방향은 유지하고,
  넓은 surface는 contract-first 또는 deferred 상태로 유지하는 것이 맞다고 평가했다.
- `3. Architecture And Boundary Review`에서 canonical identity는 current contract와
  일치하지만, local harness bot bridge에는 stale `pr_id` endpoint cleanup 후보가
  남아 있음을 확인했다.
- `4. review-engine Correctness Review`에서 canonical YAML과 generated dataset은
  현재 일치하지만, pack/profile drift와 source coverage reverse traceability 개선 후보를
  확인했다.
- `5. review-engine Authoring And Lifecycle UX Review`에서 lifecycle CLI는 좁게 유지하고,
  manual editor는 deferred로 두되, unknown YAML key를 fail-fast해야 한다는 개선 후보를
  확인했다.
- `6. review-bot Lifecycle Correctness Review`에서 runner-owned lifecycle boundary는 유지하되,
  GitLab note-trigger expected head의 never-settled path와 adapter thread/feedback identity
  scope 개선 후보를 확인했다.
- API queue validation은 TestClient startup hang으로 완료되지 않았지만, 이 신호는 Unit 6
  finding의 필수 근거가 아니므로 blocked validation으로 기록하고 리뷰 라운드는 계속 진행한다.
- `7. Provider, Fallback, And Model Backend Review`에서 lifecycle/direct provider/provider
  quality signal 분리는 유지하되, lifecycle provider runtime provenance에 model/base
  URL/transport class가 빠진 gap을 확인했다.
- `8. User Interface And Review UX Review`에서 현재 command/note surface는 유지하되,
  directed unknown command에는 GitLab-visible help/error feedback이 필요하다는 gap을 확인했다.
- `9. Ops, Smoke, And Automation Review`에서 release gate, local GitLab pre-release smoke,
  direct provider smoke의 signal 경계는 유지하되, review-roadmap blocked artifact retention과
  direct smoke preflight timeout gap을 확인했다.
- `10. Docs, Roadmap, And Deferred Review`에서 implementation roadmap과 deferred 문서의
  큰 역할 분리는 유지하되, broad watch label 보정과 private rule packaging owner 추가를
  post-review roadmap update 후보로 남겼다.
- `11. Dead Code, Dead Docs, And Cleanup Review`에서 tracked generated/cache artifact는
  발견하지 않았고, `review-engine/app/`, root `review_system.md`, TDE-named smoke internals를
  cleanup 후보로 남겼다.
- 다음에는 누적 findings가 targeted test나 smoke gate로 충분히 막혀 있는지, 그리고 어떤
  validation이 gate 역할을 못 하는지 점검한다.

## Validation Baseline

리뷰 문서 작업:

```bash
git diff --check
```

비파괴 정적 확인:

```bash
git status --short
rg -n "TODO|FIXME|deprecated|compat|fallback|legacy|watch" review-engine review-bot review-platform ops docs
```

필요 시 targeted test:

```bash
cd review-engine && uv run pytest tests/test_rule_runtime.py tests/test_rule_lifecycle_cli.py -q
cd review-bot && uv run pytest tests/test_review_runner.py tests/test_api_queue.py -q
cd review-platform && uv run pytest tests/test_pr_flow.py -q
```

runtime smoke:

```bash
bash ops/scripts/smoke_local_gitlab_lifecycle_review.sh
bash ops/scripts/smoke_openai_provider_direct.sh
```

runtime smoke는 해당 review unit이 실제 runtime evidence를 필요로 할 때만 실행한다.
