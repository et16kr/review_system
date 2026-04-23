# Review Engine Multi-Language Rule Canonicalization Completion Status

## 목적

이 문서는 현재 `review-engine` 멀티 랭귀지 canonicalization 작업의
완료 상태를 고정하고, 이번 단계에서 무엇이 닫혔는지와
앞으로 남는 일이 "미완료 구현"이 아니라 "후속 최적화"라는 점을 분리해 기록한다.

이 문서의 초점은 다음이다.

- 현재 seed source bundle 기준 core canonicalization이 완료되었는지 명확히 기록
- source-to-runtime coverage와 regression 검증 결과를 고정
- 앞으로의 일은 release-blocking 미완료가 아니라 follow-up optimization으로 분리

## 현재 결론

현재 상태는 다음과 같다.

- 멀티 랭귀지 runtime 구조는 도입되어 있다.
- 언어별 canonical `rules/**/*.yaml` pack, profile, policy는 존재한다.
- ingest와 retrieval은 언어별 dataset / collection 기준으로 동작한다.
- `rule_sources` seed bundle 전체에 대해 source-atom coverage matrix가 존재한다.
- 현재 커밋된 source bundle의 candidate/reference guidance atom에는 더 이상 `pending` 항목이 없다.
- `auto_review`와 `reference_only` 분리가 current seed bundle 기준으로 문서화되었다.
- YAML / SQL context-dialect retrieval에서 hinted rule leakage 회귀가 보정되었다.
- `YAML/CI` deepening bundle과 `SQL/warehouse` analytics bundle이 canonical source/rule/query/example까지 함께 확장되었다.
- `TypeScript/React` deepening bundle이 canonical source/rule/query/example까지 함께 확장되었다.
- `Java/Spring`, `Python/Django/FastAPI`, `Rust/Tokio`, `TypeScript/JavaScript Next.js` deepening bundle이 canonical source/rule/query/example까지 함께 확장되었다.
- `CUDA` baseline bundle이 official CUDA guidance 기반 canonical source/rule/query/example까지 함께 확장되었다.
- `CUDA`는 후속 단계에서 `cuda_async_runtime`, `cuda_multigpu` profile까지 detector-backed canonical source/rule/query/example으로 확장되었다.
- `CUDA`는 추가 단계에서 `cuda_tensor_core`, `cuda_cooperative_groups` profile까지 detector-backed canonical source/rule/query/example으로 확장되었다.
- `YAML/product_config`, `YAML/schema_config`, `SQL/dbt_warehouse`, `SQL/migration_sql`이 profile/context/dialect 축으로 실제 runtime에 연결되었다.
- provider fallback system prompt에서 C++ 고정 가정이 제거되었고, compact language tag와 profile/context routing 회귀가 보강되었다.
- provider draft 정규화가 추가되어 모델이 제목에 `[봇 리뷰][lang]` 태그나 `제목:` / `권장 수정:` 같은 헤더를 섞어도 최종 코멘트는 짧고 일관되게 정리된다.
- 언어가 비어 있는 경우 provider prompt가 더 이상 묵시적으로 `cpp` language prompt로 떨어지지 않고 base/profile prompt만 사용한다.
- `wrong-language` feedback는 event payload를 canonical source로 집계되며 `/internal/analytics/wrong-language-feedback` endpoint로 조회할 수 있다.
- wrong-language telemetry를 Markdown snapshot으로 남기는 전용 capture 스크립트가 추가되었다.
- wrong-language telemetry를 detector backlog Markdown으로 바로 내보내는 전용 builder 스크립트가 추가되었다.
- 문서형 파일은 `unknown` fallback 대신 명시적 unreviewable `markdown`으로 분류되고, root `README.md` 같은 경로도 `docs` bucket으로 집계된다.
- publish batch selection은 file별 round-robin 우선순위로 보정되어 한 파일이 batch를 독점하지 않도록 조정되었다.
- 같은 파일의 같은 라인에서 같은 category로 phrasing만 다른 후보는 batch 전에 하나로 접어서 comment density를 더 낮춘다.
- multi-line evidence snippet은 댓글에서 모든 줄이 blockquote로 렌더링되도록 보정되어 Markdown formatting이 깨지지 않는다.
- 언어별 positive / diff / false-positive regression 예제가 유지된다.
- `review-engine` 전체 회귀, `review-bot` 핵심/확장 회귀, `review-platform` 회귀가 현재 기준으로 다시 통과했다.

즉 현재는 다음 상태다.

"현재 커밋된 멀티 랭귀지 seed source bundle 기준 core canonicalization은 완료되었다."

다만 이것은 다음 의미와는 다르다.

- 외부 guideline 원문 전체를 무한정 계속 import한 상태
- 새로운 framework/product-specific source bundle 추가가 더 이상 필요 없다는 의미
- provider별 응답 품질 편차나 운영 telemetry 최적화까지 끝났다는 의미

즉 이제 남는 일은 "기존 문서에 적힌 미완료 core 작업"이 아니라
"새 source를 더 들여오거나 운영 품질을 더 높이는 후속 작업"이다.

## 이번 단계에서 닫힌 항목

### 1. Source coverage matrix atomization 완료

- `review-engine/rule_sources/coverage_matrix.yaml`는 더 이상 topic-level matrix가 아니다.
- 현재는 `coverage_granularity: source_atom` 기준으로 관리된다.
- 현재 seed source bundle의 `Candidate Canonical Rule Groups`, `Reference-Only Guidance` 섹션 bullet 수와
  coverage matrix atom 수가 일치하도록 검증된다.
- 현재 seed source bundle 기준 `pending` source atom은 없다.
- 현재 커밋된 source bundle은 `31`개이고 coverage atom은 `156`개다.
- coverage 상태는 `mapped 96`, `reference_only 60`, `pending 0`이다.

### 2. Source-to-runtime coverage closure 완료

- current seed bundle의 canonicalizable guidance는 모두 `mapped`, `reference_only`, `excluded` 중 하나로 분류되었다.
- 이번 단계에서는 current seed bundle 범위에서 `excluded` 없이 `mapped/reference_only`로 정리되었다.
- 즉 "현재 문서화된 seed source bundle"에 대해
  source-to-runtime gap은 더 이상 미분류 상태가 아니라 의도적으로 설명 가능한 상태다.

### 3. Context / dialect retrieval leakage 보정 완료

- hinted rule augmentation 뒤에도 runtime-selected pack/context/dialect 제약을 다시 적용하도록 수정했다.
- 이로써 Helm values 파일에 CI rule이 섞이거나,
  generic SQL에 dialect-specific rule이 잘못 끼어드는 회귀를 막았다.
- 이 변경은 source coverage completion뿐 아니라 ranking/policy 안정화에도 직접 기여한다.

### 4. Golden / regression 보강 완료

- source coverage matrix 전용 검증 테스트가 추가되었다.
- YAML context-specific retrieval 회귀가 추가되었다.
- SQL dialect-specific retrieval 회귀가 추가되었다.
- expected example corpus에 `.gitlab-ci.yml`, Helm values, analytics warehouse SQL example이 추가되었다.

### 5. Bot / smoke 재검증 완료

- `review-bot` 핵심 회귀를 다시 통과했다.
- local GitLab smoke를 다시 통과했다.
- 따라서 이번 단계의 retrieval / context ranking 보정이 실제 detect/publish/sync flow를 깨지 않았음이 확인되었다.

### 6. 권장 실행 순서의 1차 source 확장 완료

- 후속 작업 문서에서 가장 먼저 권장했던 `YAML/CI`, `SQL/warehouse` 확장을 실제 구현했다.
- 이번 증분은 source bundle 추가만이 아니라 canonical rule, detector/query hint, example, coverage matrix, ingest를 한 묶음으로 닫았다.

### 7. 권장 실행 순서의 2차 source 확장 완료

- 다음 우선순위였던 `TypeScript/React` 확장을 실제 구현했다.
- React/TSX 렌더링 trust boundary, async effect callback, exhaustive-deps suppression을 detector-backed canonical rule로 수용했다.
- 이번 단계에서 applicability 필터가 새 `async_effect_callback` 신호를 누락하던 회귀도 함께 수정했다.

### 8. 권장 실행 순서의 3차 framework/profile 확장 완료

- 다음 우선순위였던 `Java/Spring`, `Python/Django/FastAPI`, `Rust/Tokio`, `Next.js` 확장을 실제 구현했다.
- framework별 source bundle, canonical pack/profile, query detector, prompt overlay, expected example, regression을 한 묶음으로 추가했다.
- registry는 annotation/import/path/content 기반 고신뢰 신호가 있을 때만 framework profile/context를 선택하도록 보강되었다.

### 9. Product/config and warehouse/migration axis 완료

- `YAML/product_config`, `YAML/schema_config`, `SQL/dbt_warehouse`, `SQL/migration_sql` 축이 실제 runtime profile/context/dialect로 연결되었다.
- path/content 기반 detector와 profile/context prompt가 함께 추가되어 mixed-language PR/MR에서 파일별 라우팅이 가능하다.

### 10. Wrong-language 운영 루프 1차 구현 완료

- compact comment format을 유지하면서 wrong-language 유도 문구를 짧게 노출하도록 유지했다.
- `@review-bot wrong-language <expected-language>` 피드백은 immutable feedback event payload로 저장되고, 별도 DB migration 없이 analytics에서 집계된다.
- `/internal/analytics/wrong-language-feedback` endpoint와 runner aggregation이 추가되었다.
- `ops/scripts/build_wrong_language_backlog.py`로 telemetry를 우선순위 backlog Markdown으로 바로 정리할 수 있다.
- 문서형 파일은 explicit unreviewable `markdown`으로 분류되어 wrong-language 분석에서 `unknown` 대신 읽을 수 있는 expected/detected language를 남긴다.

### 11. 운영 telemetry / mixed-language smoke 완료

- `ops/scripts/capture_wrong_language_telemetry.py`로 wrong-language pair/profile/path/triage 후보를 바로 Markdown snapshot으로 남길 수 있다.
- `ops/scripts/build_wrong_language_backlog.py`로 wrong-language triage 후보를 `high/medium/low` backlog 형태로 바로 남길 수 있다.
- `ops/scripts/smoke_local_gitlab_multilang_review.sh`로 `markdown + yaml + sql + FastAPI` 조합 MR을 실제 GitLab에서 재현할 수 있다.
- 이 smoke는 compact language tag, markdown 비검토 경로, wrong-language feedback reply, telemetry 집계까지 한 번에 검증한다.
- 실제 smoke 실행에서 `[봇 리뷰][yaml]`, `[봇 리뷰][sql]`, `[봇 리뷰][python]`이 게시되고 `yaml -> markdown` telemetry pair가 기록됨을 다시 확인했다.

### 12. CUDA native capability expansion 완료

- `CUDA`는 baseline, async runtime, multi-GPU에 더해 `cuda_tensor_core`, `cuda_cooperative_groups` profile까지 runtime에 연결되었다.
- Tensor Core profile은 WMMA/inline MMA PTX/mixed-precision epilogue boundary를 detector-backed canonical rule로 수용한다.
- Cooperative Groups profile은 collective partitioning, divergent group sync, `grid.sync()` cooperative launch ownership을 detector-backed canonical rule로 수용한다.
- 이번 증분도 source bundle, canonical pack/profile, query detector, prompt overlay, expected example, regression을 한 묶음으로 추가했다.

## 현재 구현 범위

현재 canonical YAML rule 수는 아래와 같다.

- `bash`: `14` (`auto_review 11`, `reference_only 3`)
- `c`: `16` (`auto_review 11`, `reference_only 5`)
- `cpp`: `54` (`auto_review 44`, `reference_only 10`)
- `cuda`: `34` (`auto_review 23`, `reference_only 11`)
- `dockerfile`: `13` (`auto_review 12`, `reference_only 1`)
- `go`: `12` (`auto_review 10`, `reference_only 2`)
- `java`: `19` (`auto_review 14`, `reference_only 5`)
- `javascript`: `19` (`auto_review 14`, `reference_only 5`)
- `python`: `28` (`auto_review 18`, `reference_only 10`)
- `rust`: `17` (`auto_review 12`, `reference_only 5`)
- `shared`: `15` (`auto_review 7`, `reference_only 8`)
- `sql`: `29` (`auto_review 21`, `reference_only 8`)
- `typescript`: `26` (`auto_review 19`, `reference_only 7`)
- `yaml`: `28` (`auto_review 20`, `reference_only 8`)

총 canonical YAML rule 수는 `324`이다.

현재 ingest 기준 runtime 상태는 아래와 같다.

- total parsed: `504`
- active records: `320`
- reference records: `184`
- excluded records: `0`

언어별 ingest active/reference 상태는 아래와 같다.

- `bash`: `18 / 11`
- `c`: `18 / 13`
- `cpp`: `51 / 18`
- `cuda`: `30 / 19`
- `dockerfile`: `19 / 9`
- `go`: `17 / 10`
- `java`: `21 / 13`
- `javascript`: `21 / 13`
- `python`: `25 / 18`
- `rust`: `19 / 13`
- `sql`: `28 / 16`
- `typescript`: `26 / 15`
- `yaml`: `27 / 16`

## 검증 결과

이번 상태는 아래 검증으로 다시 확인했다.

- `python3 -m py_compile ops/scripts/build_wrong_language_backlog.py ops/scripts/capture_wrong_language_telemetry.py` -> 성공
- `cd review-engine && uv run pytest tests/test_language_registry.py tests/test_query_conversion.py tests/test_multilang_regressions.py tests/test_expected_examples.py tests/test_source_coverage_matrix.py -q` -> `54 passed`
- `cd review-bot && uv run pytest tests/test_review_runner.py -q` -> `64 passed`
- `cd review-engine && uv run python -m review_engine.cli.ingest_guidelines` -> `total_parsed 504`, `active 320`, `reference 184`
- `cd review-engine && uv run pytest -q` -> `121 passed`
- `cd review-bot && uv run pytest -q` -> `157 passed`
- `cd review-platform && uv run pytest tests/test_pr_flow.py -q` -> `3 passed`
- `bash ops/scripts/smoke_local_gitlab_multilang_review.sh --json-output /tmp/review-bot-multilang-smoke.json` -> `yaml/sql/python` language tag 게시 + `yaml -> markdown` telemetry 기록 확인
- `python3 ops/scripts/build_wrong_language_backlog.py --project-ref root/review-system-multilang-smoke --window 28d --output /tmp/review-bot-wrong-language-backlog.md` -> backlog Markdown 생성 확인

mixed-language smoke와 backlog 생성에서 아래 항목을 다시 확인했다.

- `markdown + yaml + sql + FastAPI` 조합 MR 생성 성공
- `[봇 리뷰][yaml]`, `[봇 리뷰][sql]`, `[봇 리뷰][python]` compact tag 게시 확인
- wrong-language reply 이후 `yaml -> markdown` telemetry pair 기록 확인
- telemetry 기반 backlog Markdown이 `high priority` 항목으로 실제 생성되며, `.gitlab-ci.yml -> markdown` 케이스는 non-doc mismatch 안내로 더 정확히 표현됨을 확인

이번 CUDA 증분에서는 아래 검증을 추가로 수행했다.

- `cd review-engine && uv run python -m review_engine.cli.ingest_guidelines` -> `total_parsed 504`, `active 320`, `reference 184`, `cuda active/reference 30/19`
- `cd review-engine && uv run pytest tests/test_language_registry.py tests/test_query_conversion.py tests/test_multilang_regressions.py tests/test_expected_examples.py tests/test_source_coverage_matrix.py -q` -> `54 passed`
- `cd review-engine && uv run pytest -q` -> `121 passed`
- `cd review-bot && uv run pytest tests/test_language_registry.py tests/test_review_runner.py -q` -> `70 passed`
- `cd review-bot && uv run pytest tests/test_api_queue.py tests/test_integration_phase1_4.py -q` -> `65 passed`

## 완료 기준 체크

이전 문서에서 completion 기준으로 두었던 항목은 현재 seed source bundle 기준으로 충족되었다.

1. 각 언어 source 문서에 대해 coverage matrix가 존재한다.
2. 각 source atom은 `mapped`, `reference_only`, `excluded` 중 하나로 분류된다.
3. current seed bundle 기준 `pending` atom이 없다.
4. canonical runtime rule과 source coverage 사이의 차이가 문서화된다.
5. 언어별 ingest, retrieval, prompt, bot propagation 회귀가 현재 범위에서 통과한다.
6. mixed-language PR/MR regression이 통과한다.
7. rule corpus 증가 이후에도 핵심 regression contract가 유지된다.

## 비차단 후속 작업

아래는 더 이상 "미완료 core canonicalization"이 아니라
새 소스 추가나 운영 품질 향상을 위한 follow-up optimization이다.

### 1. Provider / ranking 품질 미세조정

- 운영 provider별 comment phrasing 편차 축소
- language/profile/context 조합별 top-k ranking calibration 추가 보정
- 실제 운영 샘플 기준 false-positive/under-trigger tuning

현재 1차 보정으로 아래가 반영되었다.

- provider system hint에 `security`, `configuration`, `process`, `sql_quality`, `api_contract`, `resource_management`, `concurrency`, `performance`, `state_management` 등 멀티 랭귀지 category별 guidance block이 추가되었다.
- provider output 정규화가 추가되어 compact title, heading 제거, evidence cleanup이 provider별 phrasing 차이를 줄이도록 보정되었다.
- 언어 미지정 케이스는 더 이상 암묵적 `cpp` prompt fallback을 쓰지 않아 잘못된 language prior가 줄어들었다.
- rerank tie-breaker는 정적 `specificity/base_score`보다 먼저 `higher_pattern_boost`, `higher_similarity`를 보도록 보정되었다.
- 즉 같은 tier 안에서는 detector가 직접 힌트한 규칙과 실제 query/embedding 유사성이 top-k에 더 직접 반영된다.
- 추가 보정으로 exact `trigger_patterns` match는 token-overlap fallback보다 더 강한 `pattern_boost`를 받도록 조정되었다.
- token-overlap fallback은 overlap 비율 기반으로 낮춰, 한 단어만 겹쳐도 exact detector hit처럼 보이지 않도록 보정되었다.
- C++ detector에는 `for_initializer_declaration -> ES.6` direct hint 누락이 보강되어 기존 golden top-k contract가 다시 고정되었다.

### 2. Wrong-language telemetry 운영 사용량 축적

- `/internal/analytics/wrong-language-feedback`와 telemetry snapshot을 주기적으로 쌓아서 detector blind spot backlog를 운영 데이터 기준으로 우선순위화
- 자주 틀리는 path bucket / language pair를 기준으로 detector blind spot backlog 관리
- comment density, expected-language 안내문, batch prioritization을 운영 데이터 기준으로 다듬기

현재 2차 보정으로 아래가 반영되었다.

- wrong-language triage suggested action은 `docs` path와 "non-doc path but expected markdown"을 구분해 더 path-aware 하게 출력된다.
- 즉 `.gitlab-ci.yml -> markdown` 같은 이벤트는 더 이상 "문서 경로 exclusion 강화"로 오해하지 않고, detector 오분류인지 feedback thread 대상이 맞는지 먼저 확인하도록 안내한다.
- publish path에서는 같은 line/category 변형 코멘트를 미리 접어 batch slot 낭비를 줄였고, multi-line evidence quote도 안정화했다.

### 3. Corpus growth beyond current ecosystem set

- 현재 `rule_sources`에 없는 새 source를 더 들여와 canonical YAML로 확장
- 현재 구현한 `Spring/Django/FastAPI/Tokio/Next.js/product/schema/dbt/migration` 바깥의 외부 guideline family를 추가 수용
- 추가 소스 도입 시 coverage matrix와 regression corpus를 같은 방식으로 확장

## 후속 작업 분류

비차단 후속 작업은 모두 같은 성격이 아니다.
실행 전에 아래처럼 분류해서 다루는 것을 권장한다.

### A. 설계 문서 없이 진행 가능한 작업

아래 작업은 현재 구조를 유지한 채 tuning/corpus 범위를 넓히는 일이므로
기존 완료 상태 문서만 갱신해도 충분하다.

- provider prompt wording 보정
- wrong-language telemetry 해석 루프 정리
- mixed-language smoke fixture 추가
- current ecosystem 바깥 guideline family 추가 수용
- 새 source에 맞춘 canonical YAML rule / coverage / regression 확장

### B. 짧은 설계 메모가 권장되는 작업

아래 작업은 구조를 뒤집지는 않지만,
ranking / prompting / 운영 동작 품질에 실제 영향을 주므로
1~2페이지 수준의 짧은 설계 메모를 두는 편이 좋다.

- provider별 prompt 품질 차이 축소
- 멀티 랭귀지 응답 편차 축소
- comment density 보정
- batch prioritization 보정
- comment publishing priority calibration 고도화
- wrong-language feedback telemetry 운영 기준과 backlog triage 방식 정리

### C. 별도 설계 문서가 필요한 조건부 작업

아래는 현재 후속 작업 자체가 아니라,
후속 작업을 하다가 이런 변경이 생기는 경우에 별도 설계 문서가 필요하다는 의미다.

- provider prompt contract 자체를 변경하는 경우
- `review-bot` 사용자 피드백 명령 / 태그 / workflow를 바꾸는 경우
- telemetry 저장 구조나 DB schema가 바뀌는 경우
- 새 API/CLI contract를 추가하는 경우
- profile / context / dialect 모델 자체를 확장하는 경우

## 권장 실행 순서

비차단 후속 작업은 아래 순서를 권장한다.

### 1. 운영 telemetry 루프부터 닫기

- `wrong-language-feedback` endpoint를 실제 운영 점검 루프에 넣는다.
- 자주 틀리는 `language pair/profile/path bucket`을 우선 detector backlog로 만든다.

### 2. Provider / ranking tuning 진행

- provider별 prompt phrasing 차이 축소
- comment density / batch prioritization 보정
- profile/context별 top-k ranking calibration

### 3. Mixed-language smoke fixture 보강

- 기존 smoke는 유지하되 framework/product/config 조합을 더 직접 검증하는 fixture를 추가한다.
- 특히 `markdown + yaml + sql + framework file` 조합에서 compact tag와 wrong-language reply 흐름을 확인한다.

### 4. 그 다음 추가 source 확장

- 현재 ecosystem 세트 바깥의 새 source를 들여올 때는
  여전히 `source + canonical rule + coverage + regression`을 한 묶음으로 닫는다.

### 5. 구조 변경이 생기면 그때 별도 설계 문서 작성

- API
- DB
- workflow
- prompt contract
- feedback UX

이런 축이 바뀌는 시점에만 별도 설계 문서를 추가한다.

## 실무용 한 줄 정리

가장 실무적인 실행 방식은 다음과 같다.

"먼저 새 source와 rule corpus를 계속 넓히고, 그 다음 provider 품질을 다듬고, 마지막으로 운영 telemetry와 feedback loop를 정리하며, 구조 변경이 생길 때만 별도 설계 문서를 쓴다."

## 짧은 표현

한 문장으로 요약하면 다음과 같다.

"현재 커밋된 멀티 랭귀지 ecosystem 세트 기준으로 source-atom coverage, runtime canonicalization, framework/profile routing, wrong-language analytics, retrieval regression까지 모두 닫혔고, 이제 남는 일은 운영 최적화와 추가 ecosystem 확장이다."
