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
- 언어별 positive / diff / false-positive regression 예제가 유지된다.
- `review-engine` 전체 회귀, `review-bot` 핵심 회귀, local GitLab smoke가 현재 기준으로 다시 통과했다.

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
- expected example corpus에 `.gitlab-ci.yml`, Helm values example이 추가되었다.

### 5. Bot / smoke 재검증 완료

- `review-bot` 핵심 회귀를 다시 통과했다.
- local GitLab smoke를 다시 통과했다.
- 따라서 이번 단계의 retrieval / context ranking 보정이 실제 detect/publish/sync flow를 깨지 않았음이 확인되었다.

## 현재 구현 범위

현재 canonical YAML rule 수는 아래와 같다.

- `bash`: `14` (`auto_review 11`, `reference_only 3`)
- `c`: `16` (`auto_review 11`, `reference_only 5`)
- `cpp`: `54` (`auto_review 44`, `reference_only 10`)
- `dockerfile`: `13` (`auto_review 12`, `reference_only 1`)
- `go`: `12` (`auto_review 10`, `reference_only 2`)
- `java`: `13` (`auto_review 10`, `reference_only 3`)
- `javascript`: `13` (`auto_review 10`, `reference_only 3`)
- `python`: `18` (`auto_review 12`, `reference_only 6`)
- `rust`: `12` (`auto_review 9`, `reference_only 3`)
- `shared`: `15` (`auto_review 7`, `reference_only 8`)
- `sql`: `15` (`auto_review 12`, `reference_only 3`)
- `typescript`: `15` (`auto_review 12`, `reference_only 3`)
- `yaml`: `18` (`auto_review 13`, `reference_only 5`)

총 canonical YAML rule 수는 `228`이다.

현재 ingest 기준 runtime 상태는 아래와 같다.

- total parsed: `393`
- active records: `250`
- reference records: `143`
- excluded records: `0`

언어별 ingest active/reference 상태는 아래와 같다.

- `bash`: `18 / 11`
- `c`: `18 / 13`
- `cpp`: `51 / 18`
- `dockerfile`: `19 / 9`
- `go`: `17 / 10`
- `java`: `17 / 11`
- `javascript`: `17 / 11`
- `python`: `19 / 14`
- `rust`: `16 / 11`
- `sql`: `19 / 11`
- `typescript`: `19 / 11`
- `yaml`: `20 / 13`

## 검증 결과

이번 상태는 아래 검증으로 다시 확인했다.

- `cd review-engine && uv run pytest -q` -> `89 passed`
- `cd review-engine && uv run python -m review_engine.cli.ingest_guidelines` -> 성공
- `cd review-bot && uv run pytest tests/test_review_runner.py tests/test_language_registry.py -q` -> `59 passed`
- `bash ops/scripts/smoke_local_gitlab_tde_review.sh` -> `smoke_validation.passed = true`

smoke에서 확인된 핵심 조건은 아래와 같다.

- baseline review 성공
- baseline review failed publication `0`
- baseline review thread 생성 확인
- 3회 incremental replay 성공
- human reply / resolve / sync flow 성공
- sync 이후 feedback 증가 확인
- resolve 이후 open thread 감소 확인

## 완료 기준 체크

이전 문서에서 completion 기준으로 두었던 항목은 현재 seed source bundle 기준으로 충족되었다.

1. 각 언어 source 문서에 대해 coverage matrix가 존재한다.
2. 각 source atom은 `mapped`, `reference_only`, `excluded` 중 하나로 분류된다.
3. current seed bundle 기준 `pending` atom이 없다.
4. canonical runtime rule과 source coverage 사이의 차이가 문서화된다.
5. 언어별 ingest, retrieval, prompt, bot propagation 회귀가 현재 범위에서 통과한다.
6. mixed-language PR/MR regression 및 smoke가 통과한다.
7. rule corpus 증가 이후에도 핵심 regression contract가 유지된다.

## 비차단 후속 작업

아래는 더 이상 "미완료 core canonicalization"이 아니라
새 소스 추가나 운영 품질 향상을 위한 follow-up optimization이다.

### 1. New source expansion

- framework-specific source bundle 추가
- product-specific YAML/CI/schema bundle 추가
- warehouse / dbt / migration-specific SQL source 확장
- React / Next.js / Spring / Tokio 등 생태계별 확장 source 추가

### 2. Provider quality tuning

- provider별 prompt 품질 차이 축소
- 멀티 랭귀지 응답 편차 축소
- comment density / batch prioritization 추가 보정

### 3. Operational feedback loop

- wrong-language feedback telemetry 정리
- 운영 트래픽 기반 재학습 또는 재조정 루프 정리
- comment publishing priority calibration 고도화

### 4. Corpus growth beyond current seed bundle

- 현재 `rule_sources`에 없는 새 source를 더 들여와 canonical YAML로 확장
- current seed bundle 바깥의 외부 guideline family를 추가 수용
- 추가 소스 도입 시 coverage matrix와 regression corpus를 같은 방식으로 확장

## 후속 작업 분류

비차단 후속 작업은 모두 같은 성격이 아니다.
실행 전에 아래처럼 분류해서 다루는 것을 권장한다.

### A. 설계 문서 없이 진행 가능한 작업

아래 작업은 현재 구조를 유지한 채 corpus와 regression 범위를 넓히는 일이므로
기존 완료 상태 문서만 갱신해도 충분하다.

- framework-specific source bundle 추가
- product-specific YAML/CI/schema bundle 추가
- warehouse / dbt / migration-specific SQL source 확장
- current seed bundle 바깥 guideline family 추가 수용
- 새 source에 맞춘 canonical YAML rule 추가
- coverage matrix 확장
- expected example / golden / false-positive regression 확장

### B. 짧은 설계 메모가 권장되는 작업

아래 작업은 구조를 뒤집지는 않지만,
ranking / prompting / 운영 동작 품질에 실제 영향을 주므로
1~2페이지 수준의 짧은 설계 메모를 두는 편이 좋다.

- provider별 prompt 품질 차이 축소
- 멀티 랭귀지 응답 편차 축소
- comment density 보정
- batch prioritization 보정
- comment publishing priority calibration 고도화
- wrong-language feedback telemetry 수집 범위와 활용 방식 정리

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

### 1. Source 확장부터 진행

- framework/product-specific source bundle을 먼저 추가
- 가장 ROI가 높은 순서로는 `YAML/CI`, `SQL/warehouse`, `TypeScript/React`, `Java/Spring`, `Python/framework`, `Rust async ecosystem` 계열을 권장
- 이유는 corpus가 넓어져야 이후 provider tuning과 telemetry tuning도 실제 데이터 기반으로 할 수 있기 때문이다

### 2. Source 추가 직후 canonicalization과 coverage를 같이 닫기

- 새 source bundle 추가
- canonical YAML rule 추가
- coverage matrix atom 추가
- expected example / regression 추가
- ingest 및 retrieval 회귀 확인

즉 source를 넣고 나중에 테스트를 붙이는 방식보다
"source + canonical rule + coverage + regression"을 한 묶음으로 닫는 것이 좋다.

### 3. Corpus가 넓어진 뒤 provider quality tuning 진행

- provider별 prompt 품질 차이 축소
- 멀티 랭귀지 응답 편차 축소
- context/dialect별 comment phrasing 보정

이 단계는 corpus가 충분히 넓어진 뒤에 해야
특정 fixture에만 맞춘 tuning으로 좁아지는 것을 피할 수 있다.

### 4. 운영 feedback loop 정리

- wrong-language feedback telemetry 정리
- 운영 트래픽 기준 재조정 루프 정리
- comment density / batch prioritization 보정

이 단계는 실제 운영 데이터가 있어야 가치가 크므로
source/corpus 확장과 provider tuning 이후에 두는 것이 낫다.

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

"현재 커밋된 멀티 랭귀지 seed source bundle 기준으로 source-atom coverage, runtime canonicalization, retrieval regression, bot smoke까지 모두 닫혔고, 이제 남는 일은 새 source 확장과 운영 최적화다."
