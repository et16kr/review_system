# Review Roadmap

## Purpose

이 문서는 구현 roadmap과 별도로, 현재 저장소를 처음부터 다시 점검하기 위한 리뷰 계획을 관리한다.
목표는 다음 세 가지다.

1. 현재 방향성이 맞는지 확인한다.
2. 버그, 불일치, 과도한 복잡도, 남아 있는 불필요한 흔적을 찾는다.
3. 리뷰 결과를 실행 가능한 후속 작업으로 다시 정리한다.

이 문서는 코드 구현보다 `검토`, `증거 수집`, `리뷰 문서 축적`을 중심으로 진행한다.

마지막 코드 상태 점검일: `2026-04-24`

상태 표기:

- `active`: 지금 바로 리뷰 단위로 실행 가능하다.
- `partial`: 일부 리뷰 산출물은 있지만 아직 결론이 덜 모였다.
- `queued`: 앞선 리뷰 결과가 모이면 바로 이어서 할 수 있다.
- `watch`: 이번 리뷰 라운드에서는 새 작업이 없다.

## Review Outputs

이 roadmap을 진행할 때 누적 산출물은 아래 문서를 기준으로 관리한다.

- [docs/reviews/CURRENT_STATE_REVIEW.md](/home/et16/work/review_system/docs/reviews/CURRENT_STATE_REVIEW.md:1)
  - findings-first 현재 상태 리뷰 본문
- [docs/reviews/REVIEW_FINDINGS_BACKLOG.md](/home/et16/work/review_system/docs/reviews/REVIEW_FINDINGS_BACKLOG.md:1)
  - 후속 작업 후보와 severity / area / action owner 정리

원칙:

- 한 리뷰 unit은 위 문서 중 하나 이상을 실제로 갱신해야 한다.
- 리뷰만 하는 단위에서는 코드 수정 없이 문서와 증거만 남겨도 된다.
- 필요 시 비파괴 검증은 허용하지만, smoke나 외부 API 의존 검증은 해당 review unit이 정말 필요로 할 때만 쓴다.

## Current Snapshot

이미 완료된 기반:

- provider runtime provenance / guardrails
- smoke / evaluation hardening
- organization extension canonicalization
- roadmap automation blocked artifact retention
- minimal rule lifecycle CLI

현재 리뷰에서 특히 다시 확인할 축:

1. `review-engine` rule / retrieval / authoring 경계
2. `review-bot` lifecycle / provider / UX / config 경계
3. ops smoke / replay / automation의 실제 신뢰성
4. 문서와 실제 코드 상태의 일치 여부
5. 더 이상 필요 없는데 남아 있는 코드, 문서, 설정, 스크립트

## Now

### 1. Review Frame And Evidence Inventory

상태: `watch`

이번 작업의 범위:

1. `docs/reviews/CURRENT_STATE_REVIEW.md`의 기본 구조를 만든다.
2. 이번 리뷰에서 볼 시스템 영역과 주요 근거 파일을 표로 고정한다.
3. 어떤 검증은 정적 읽기만으로 충분하고, 어떤 검증은 실행이 필요한지 구분한다.
4. 누적 findings 형식을 severity / evidence / impact / action으로 고정한다.

완료 기준:

- 이후 review unit이 같은 형식으로 findings를 누적할 수 있다.
- 리뷰 범위와 evidence source가 문서에서 명확하다.

`2026-04-24` 업데이트:

- [docs/reviews/CURRENT_STATE_REVIEW.md](/home/et16/work/review_system/docs/reviews/CURRENT_STATE_REVIEW.md:1)에 review scope, evidence inventory, validation mode split, finding contract를 고정했다.
- [docs/reviews/REVIEW_FINDINGS_BACKLOG.md](/home/et16/work/review_system/docs/reviews/REVIEW_FINDINGS_BACKLOG.md:1)에 backlog intake rule과 field contract를 고정했다.
- 이번 unit은 문서 프레임 정리만 수행했으므로 runtime test, local GitLab smoke, provider-direct smoke는 실행하지 않았다.

### 2. Architecture And Direction Review

상태: `watch`

이번 작업의 범위:

1. `CURRENT_SYSTEM.md`, `README.md`, `AGENTS.md`, `API_CONTRACTS.md`를 기준으로 현재 아키텍처 방향을 다시 점검한다.
2. canonical invariant가 코드 구조와 실제로 맞는지 본다.
3. harness / platform / bot / engine 경계가 과도하게 섞였는지 확인한다.
4. 방향성은 맞지만 문서가 뒤처진 부분과, 반대로 문서만 남고 실제 가치가 떨어진 부분을 적는다.

완료 기준:

- 현재 방향성이 맞는지에 대한 1차 결론이 문서에 남는다.
- 큰 구조 리스크가 있으면 severity와 함께 정리된다.

`2026-04-24` 업데이트:

- [docs/reviews/CURRENT_STATE_REVIEW.md](/home/et16/work/review_system/docs/reviews/CURRENT_STATE_REVIEW.md:1)에 architecture/direction review 결과를 추가했고, top-level 방향성은 유지하되 local harness compatibility seam이 current-state 문구보다 넓다는 점을 finding으로 남겼다.
- [docs/reviews/REVIEW_FINDINGS_BACKLOG.md](/home/et16/work/review_system/docs/reviews/REVIEW_FINDINGS_BACKLOG.md:1)에 `review-platform` bot facade의 stale legacy endpoint 의존성과 runner-level legacy identity helper 정리 후속 작업을 backlog로 승격했다.
- 이번 unit은 문서와 코드의 정적 evidence review만 수행했으므로 targeted test, local GitLab smoke, provider-direct smoke는 실행하지 않았다.

### 3. `review-engine` Deep Review

상태: `watch`

이번 작업의 범위:

1. rule source / profile / policy / ingest / retrieval / metadata 경계를 점검한다.
2. 최근 targeted expansion이 실제로 source/rule/detector/example/validation 묶음을 지키는지 본다.
3. rule lifecycle CLI가 canonical YAML 경계를 흐리지 않는지 본다.
4. manual editor를 미루는 현재 판단이 적절한지 다시 평가한다.
5. 중복 source, 과한 alias, 더 이상 필요 없는 authoring 표면이 남았는지 적는다.

완료 기준:

- `review-engine` 영역의 핵심 findings가 누적 리뷰 문서에 정리된다.
- 유지할 것, 줄일 것, deferred로 남길 것이 구분된다.

`2026-04-24` 업데이트:

- [docs/reviews/CURRENT_STATE_REVIEW.md](/home/et16/work/review_system/docs/reviews/CURRENT_STATE_REVIEW.md:1)에 `review-engine` deep review 결과를 추가했고, minimal lifecycle CLI와 source coverage matrix가 canonical YAML write boundary를 잘 지키는 반면, duplicate `pack_id`/`policy_id` collision은 runtime loader와 lifecycle CLI에서 조용히 덮어써진다는 finding을 남겼다.
- [docs/reviews/REVIEW_FINDINGS_BACKLOG.md](/home/et16/work/review_system/docs/reviews/REVIEW_FINDINGS_BACKLOG.md:1)에 duplicate identity collision fail-fast direct fix와 manual editor deferred 유지 판단을 backlog로 정리했다.
- 이번 unit은 docs/code static evidence review로 처리해 deterministic validation은 `git diff --check`만 사용했다. targeted test, local GitLab smoke, provider-direct smoke는 새 runtime claim이 없어 생략했고, direct OpenAI와 stub fallback도 사용하지 않았다.

### 4. `review-bot` Deep Review

상태: `active`

이번 작업의 범위:

1. detect / publish / sync / verify lifecycle 경계를 다시 점검한다.
2. provider fallback, direct smoke, provider provenance가 실제로 혼동 없이 드러나는지 본다.
3. `summarize`, `walkthrough`, `backlog`, `full-report`, `.review-bot.yaml`, `ask`의 UX 방향이 적절한지 평가한다.
4. config, API, analytics, note command surface에 불필요하게 넓어진 부분이 없는지 찾는다.
5. note-first UX에 비해 너무 이른 기능이나, 반대로 빠진 안전장치가 없는지 적는다.

완료 기준:

- `review-bot` 영역의 방향, 버그 위험, 과도한 surface가 정리된다.
- `.review-bot.yaml` / `ask`가 왜 blocked였는지와 다음 조치가 리뷰 문서에 반영된다.

### 5. Ops / Smoke / Automation Review

상태: `active`

이번 작업의 범위:

1. local GitLab smoke, multilang smoke, provider-direct smoke, roadmap automation을 다시 점검한다.
2. “통과하지만 신호가 약한 테스트”와 “실제로 gate 역할을 하는 테스트”를 구분한다.
3. blocked artifact, skip policy, review automation 문구가 운영상 충분한지 본다.
4. 환경 의존성이 강한데 문서/스크립트에서 충분히 드러나지 않는 부분을 찾는다.
5. 중복 스크립트, 명칭 혼란, 죽은 wrapper가 남아 있는지 확인한다.

완료 기준:

- ops / smoke / automation의 신뢰 경계가 문서에 재정리된다.
- 유지 / 축소 / 분리 후보가 backlog에 들어간다.

## Queue

### 6. Dead Weight And Cleanup Review

상태: `queued`

이번 작업의 범위:

1. 더 이상 쓰이지 않는 문서, wrapper, 설정, compatibility path를 찾는다.
2. 이름은 남았지만 실제 역할이 끝난 항목을 적는다.
3. cleanup이 안전한지, compatibility 때문에 유지해야 하는지 구분한다.

완료 기준:

- “없애도 되는 것”과 “호환 때문에 남겨야 하는 것”이 분리된다.

### 7. Roadmap / Deferred Reassessment

상태: `queued`

이번 작업의 범위:

1. 구현 roadmap과 deferred 문서 구성이 현재 코드 상태와 맞는지 다시 평가한다.
2. 지금 `ROADMAP.md`에 있는 것이 정말 즉시 실행 가능 항목인지 본다.
3. deferred에 있으나 다시 끌어올려야 할 항목이 있는지 본다.

완료 기준:

- roadmap / deferred 재배치 제안이 리뷰 문서에 남는다.

### 8. Consolidated Review Outcome

상태: `queued`

이번 작업의 범위:

1. 누적 findings를 severity 순으로 다시 정렬한다.
2. 즉시 수정할 것, 다음 roadmap에 넣을 것, deferred로 남길 것을 최종 분류한다.
3. `REVIEW_FINDINGS_BACKLOG.md`를 후속 실행용 backlog로 정리한다.

완료 기준:

- 이번 리뷰 라운드의 최종 결론과 후속 작업이 한 번에 보인다.

## Suggested Next Step

현재 가장 자연스러운 다음 단계는 `4. review-bot Deep Review`다.

이유:

- architecture review와 `review-engine` deep review로 top-level 방향성, harness compatibility drift, engine authoring boundary까지 한 번 정리됐으므로 이제 lifecycle/provider/UX surface가 더 큰 미확인 영역으로 남았다.
- `review-engine`에서는 duplicate identity collision과 manual editor deferred 판단을 이미 backlog/deferred로 고정했기 때문에, 다음 단계는 `review-bot`의 detect/publish/sync/verify 경계와 provider signal 분리를 같은 finding contract로 점검하는 편이 맞다.

## Validation Baseline

`2026-04-24` unit 1 실행 메모:

- docs-only review frame 작업이라 `git diff --check`만 deterministic validation으로 사용한다.
- targeted test, local GitLab smoke, provider-direct smoke는 runtime claim이 없는 이번 unit 범위 밖이라 생략한다.

`2026-04-24` unit 2 실행 메모:

- architecture/direction review도 docs/code static evidence unit으로 처리해 `git diff --check`만 deterministic validation으로 사용한다.
- targeted test, local GitLab smoke, provider-direct smoke는 runtime claim을 새로 만들지 않는 범위라 생략한다.

`2026-04-24` unit 3 실행 메모:

- `review-engine` deep review도 docs/code static evidence unit으로 처리해 `git diff --check`만 deterministic validation으로 사용한다.
- targeted test, local GitLab smoke, provider-direct smoke는 runtime claim을 새로 만들지 않는 범위라 생략한다.
- 이번 unit은 provider나 lifecycle runtime 검증을 다루지 않았으므로 direct OpenAI와 stub fallback은 둘 다 사용하지 않았다.

리뷰 문서 작업:

```bash
git diff --check
```

비파괴 정적 확인:

```bash
git status --short
rg -n "TODO|FIXME|deprecated|compat|fallback|watch" review-engine review-bot ops docs
```

필요 시 targeted test:

```bash
cd review-engine && uv run pytest tests/test_rule_runtime.py tests/test_rule_lifecycle_cli.py -q
cd review-bot && uv run pytest tests/test_review_runner.py tests/test_api_queue.py -q
```

local smoke, direct provider validation, OpenAI 비교 실행은 해당 review unit이 실제 runtime evidence를 필요로 할 때만 추가한다.
