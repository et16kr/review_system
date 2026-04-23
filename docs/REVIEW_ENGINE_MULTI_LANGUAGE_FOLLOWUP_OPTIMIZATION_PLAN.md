# Review Engine Multi-Language Follow-Up Optimization Plan

## 목적

이 문서는 현재 멀티 랭귀지 코어 runtime / rule corpus / framework profile /
wrong-language analytics가 이미 닫힌 상태를 전제로,
그 이후에 진행할 **후속 최적화 작업만** 별도로 기록한다.

이 문서의 목적은 다음과 같다.

- 지금까지 진행하던 최적화 흐름을 CUDA 작업 전에 따로 고정
- 앞으로 해야 할 최적화 항목만 분리해서 추적
- 코어 범위 확장과 운영 품질 튜닝을 혼동하지 않도록 경계 명시

새 CUDA capability 자체를 추가하는 작업은 별도 문서인
`docs/REVIEW_ENGINE_CUDA_NATIVE_CAPABILITY_EXPANSION_PLAN.md`
에서 관리한다.

현재는 `CUDA` capability expansion이 baseline + follow-up profile 단계까지
이미 반영되었으므로,
이 문서에서는 **기존 CUDA 축의 최적화 작업도 포함**한다.

## 범위

이 문서에 포함되는 것은 다음과 같다.

- provider phrasing / draft normalization / comment density 추가 튜닝
- retrieval / ranking / hinted rule calibration 추가 보정
- wrong-language telemetry 운영 루프 정착
- mixed-language smoke / evaluation / regression 보강
- 운영 기준과 triage 기준 정리
- 이미 추가된 `CUDA` 축
  - `cuda/default`
  - `cuda_async_runtime`
  - `cuda_multigpu`
  - `cuda_tensor_core`
  - `cuda_cooperative_groups`
  에 대한 retrieval, phrasing, telemetry, smoke 최적화

이 문서에 포함되지 않는 것은 다음과 같다.

- 새 `language_id` 추가
- 새 framework/profile/context/dialect 축 추가
- current ecosystem 바깥 새 guideline source 도입
- DB schema 변경
- 외부 API / CLI contract 변경
- 새로운 CUDA capability expansion
  - 예: `cuda::pipeline/cp.async`, `thread_block_cluster`, `TMA`, `wgmma`, `multi-node NCCL`, `NVSHMEM`
  - 즉 기존 CUDA 축의 품질 향상은 이 문서 범위지만, 새 CUDA 축 추가는 이 문서 범위가 아니다.

즉 `CUDA` 전체가 이 문서의 범위 밖인 것은 아니다.
현재 문서의 기준은 다음과 같다.

- 이미 구현된 CUDA 축의 **최적화**는 포함
- 아직 없는 CUDA 축의 **신규 capability expansion**은 제외

## 현재 전제

이 문서는 아래 상태를 전제로 한다.

- 멀티 랭귀지 core canonicalization은 현재 seed source bundle 기준으로 완료되어 있다.
- `wrong-language` feedback event 저장과 analytics endpoint는 이미 동작한다.
- compact comment format과 language tag는 이미 적용되어 있다.
- provider fallback prompt의 C++ 고정 가정은 제거되었다.
- round-robin batch selection, same-line/category duplicate suppression, multiline evidence quote 안정화는 이미 반영되었다.
- mixed-language smoke는 `markdown + yaml + sql + framework file` 조합까지 한 번 통과한 상태다.
- CUDA는 `default`, `cuda_async_runtime`, `cuda_multigpu`, `cuda_tensor_core`, `cuda_cooperative_groups` profile까지 canonical source/rule/query/example/regression이 연결된 상태다.

따라서 남은 일은 “기능 미구현”이 아니라
정확도, 일관성, 운영 해석성을 더 높이는 최적화다.

## 최적화 작업 항목

### 1. Wrong-Language Telemetry 운영 루프 고도화

목표는 `wrong-language` 데이터를 단순 저장이 아니라
실제 detector tuning backlog로 연결하는 것이다.

해야 할 일:

- `/internal/analytics/wrong-language-feedback`를 정기 점검 루프에 넣는다.
- `detected_language_id / expected_language_id / profile_id / context_id / path_pattern` 기준으로
  자주 반복되는 오분류 pair를 주간 backlog로 정리한다.
- `ops/scripts/capture_wrong_language_telemetry.py`,
  `ops/scripts/build_wrong_language_backlog.py` 산출물을 운영 점검 표준으로 고정한다.
- `docs` path, non-doc path but expected `markdown`, CI path, schema/product path처럼
  triage 방식이 다른 bucket을 운영 문서 기준으로 분리한다.
- wrong-language reply가 실제 detector blind spot인지,
  human reply 대상 thread 오류인지, policy mismatch인지 구분 기준을 정리한다.

완료 기준:

- wrong-language backlog를 운영 데이터로 주기적으로 생성할 수 있다.
- 자주 틀리는 path bucket과 language pair가 backlog 우선순위로 바로 읽힌다.
- detector 보강 후보와 단순 운영 오분류를 문서 기준으로 분리할 수 있다.

### 2. Provider Phrasing / Draft Quality 추가 튜닝

목표는 provider가 언어와 프로필이 달라도
과하게 장황하거나 들쭉날쭉한 phrasing 없이
짧고 근거 중심의 코멘트를 안정적으로 생성하게 만드는 것이다.

해야 할 일:

- provider별 제목 길이, summary 밀도, suggested fix 길이 편차를 측정한다.
- language/profile/context 조합별로 과하게 generic한 표현과
  과하게 장황한 표현을 줄이는 prompt tuning을 진행한다.
- evidence snippet이 짧은 코멘트에서 핵심 근거가 먼저 드러나도록
  phrasing 순서를 더 좁게 고정한다.
- CUDA 코멘트에서는 kernel launch / stream / sync / device ownership 근거가
  generic 성능 문장보다 먼저 드러나는지 따로 확인한다.
- 같은 문제를 다른 표현으로 반복하는 현상이 남아 있으면
  draft normalization 또는 publish 전 suppression 기준을 더 보강한다.
- provider 간 comment tone 차이를 줄이되,
  실제 defect claim strength까지 같이 약해지지 않도록 확인한다.

완료 기준:

- 동일 finding class에서 provider별 제목/본문 편차가 줄어든다.
- summary가 근거 없는 추상 문장보다 실제 변경 코드에 더 밀착된다.
- 장황한 fix guidance가 줄고, 한 가지 수정 방향 중심으로 수렴한다.

### 3. Retrieval / Ranking Calibration 추가 보정

목표는 rule 수가 늘어난 상태에서도
핵심 defect rule이 top-k에서 안정적으로 유지되고,
reference-only richness가 defect claim 품질을 해치지 않도록 하는 것이다.

해야 할 일:

- language/profile/context별 expected example을 기준으로 top-k drift를 점검한다.
- `priority_tier`, `base_score`, `specificity`, `pattern_boost`,
  hinted rule boost의 조합을 언어별로 다시 보정한다.
- direct detector hit, exact `trigger_patterns` hit,
  token-overlap fallback의 상대 우선순위를 계속 검증한다.
- 새 rule 추가 없이도 retrieval 순위만 흔들리는 케이스를 regression으로 고정한다.
- `reference_only`가 inline defect claim 상위권을 오염시키는지 지속 확인한다.
- CUDA에서는 `default`, `cuda_async_runtime`, `cuda_multigpu`, `cuda_tensor_core`, `cuda_cooperative_groups` 각각에 대해
  direct detector hit가 generic CUDA baseline 또는 shared rule보다 안정적으로
  먼저 오는지 별도 점검한다.
- CUDA async / multi-GPU 규칙이 같은 파일에서 baseline 규칙과 경쟁할 때
  핵심 profile-specific rule이 top-k에서 밀리지 않도록 보정한다.

완료 기준:

- 핵심 golden contract가 provider 변경이나 minor tuning 뒤에도 유지된다.
- exact detector hit가 semantic overlap보다 안정적으로 먼저 온다.
- `reference_only` richness는 유지하되 defect claim precision은 떨어지지 않는다.
- CUDA profile-specific top-k contract가 튜닝 뒤에도 유지된다.

### 4. Comment Density / Batch Prioritization 최적화

목표는 한 run에서 사용자가 실제로 읽어야 할 코멘트만
더 압축해서 보여 주는 것이다.

해야 할 일:

- file별 round-robin 이후에도 과밀하게 느껴지는 케이스를 운영 샘플로 수집한다.
- 같은 파일 / 같은 라인 / 같은 category가 아니더라도
  사실상 같은 defect class로 보이는 케이스가 있는지 점검한다.
- batch slot을 차지할 가치가 낮은 weak candidate를 더 일찍 backlog로 미루는 기준을 검토한다.
- existing open thread update, new finding, reminder candidate 사이 우선순위를 운영 관점에서 점검한다.
- compact comment format을 유지하면서도,
  “왜 이 finding이 먼저 게시되었는지”를 설명 가능한 상태로 유지한다.
- CUDA 파일에서는 같은 위치의 launch/sync/perf 류 코멘트가
  사실상 같은 defect class인지 점검해 중복 게시를 더 줄인다.

완료 기준:

- 한 파일이 batch를 독점하는 체감이 더 줄어든다.
- 같은 의미의 코멘트가 서로 다른 표현으로 동시에 뜨는 빈도가 더 줄어든다.
- 사용자가 읽는 comment 수 대비 실제 유효 defect density가 높아진다.

### 5. Mixed-Language Smoke / Evaluation 강화

목표는 현재 한 번 통과한 mixed-language 검증을
지속 회귀로 굳히는 것이다.

해야 할 일:

- 현재 smoke를 유지하면서 framework/product/config 조합 fixture를 더 늘린다.
- `markdown + yaml + sql + framework file` 외에도
  profile/context가 섞인 조합을 점진적으로 추가한다.
- provider를 `stub/stub`로 돌렸을 때와 실제 provider를 썼을 때의
  차이를 비교할 수 있는 검증 루틴을 보강한다.
- wrong-language reply 이후 telemetry 반영과 backlog 생성까지
  E2E로 점검하는 절차를 고정한다.
- retrieval contract, prompt routing, comment publishing을 한 번에 보는
  evaluation snapshot을 남길 수 있게 정리한다.
- mixed-language smoke에 `cuda/default`, `cuda_async_runtime`, `cuda_multigpu`, `cuda_tensor_core`, `cuda_cooperative_groups`
  중 최소 하나 이상이 포함된 fixture를 단계적으로 추가한다.
- CUDA가 섞인 PR/MR에서 language tag, profile routing, wrong-language feedback,
  top-k contract를 함께 보는 evaluation snapshot을 남긴다.

완료 기준:

- mixed-language smoke가 일회성 검증이 아니라 지속 회귀 수단이 된다.
- prompt routing / language tag / wrong-language feedback 흐름이 반복 검증된다.
- 운영 중 회귀가 나도 smoke 또는 targeted regression에서 빠르게 재현된다.
- CUDA가 섞인 mixed-language regression도 같은 수준으로 재현 가능하다.

### 6. 운영 문서 / Triage 기준 정리

목표는 코드 수정 없이도
운영자가 현재 시스템을 읽고 대응할 수 있는 수준까지
문서와 판단 기준을 정리하는 것이다.

해야 할 일:

- wrong-language telemetry 해석 기준을 운영 문서에 더 구체화한다.
- provider phrasing 품질 점검 항목을 간단한 체크리스트로 만든다.
- ranking drift를 볼 때 확인할 우선 지표를 문서로 남긴다.
- detector blind spot, provider overclaim, comment density 문제를
  서로 다른 카테고리로 구분하는 triage 규칙을 정리한다.
- CUDA는 `wrong-language`, `detector miss`, `profile miss`, `ranking drift`,
  `performance overclaim`을 구분해서 triage하는 기준을 추가한다.

완료 기준:

- 운영자가 회귀를 보았을 때 어떤 문서와 스크립트를 먼저 볼지 명확하다.
- comment 품질, detector 품질, ranking 품질을 서로 다른 문제로 분리해 다룰 수 있다.

### 7. CUDA Capability Expansion Handoff Optimization

목표는 별도 CUDA capability expansion 문서에서 새 축이 추가된 뒤,
그 축의 운영 품질을 다른 멀티 랭귀지 최적화와 같은 루프로 흡수하는 것이다.

해야 할 일:

- `cuda_pipeline_async`, `cuda_thread_block_cluster`, `cuda_tma`, `cuda_wgmma`가 추가되면
  기존 CUDA 최적화 checklist에 같은 방식으로 편입한다.
- provider phrasing에서는 capability별 핵심 근거가 generic 성능 문장보다 먼저 드러나는지 확인한다.
- ranking에서는 새 capability direct detector hit가
  generic CUDA baseline / tensor-core / cooperative-groups rule보다 앞서는지 점검한다.
- wrong-language / profile-miss telemetry는 capability 단위로 분리해 backlog를 만들 수 있게 본다.
- mixed-language smoke와 evaluation snapshot에
  capability별 representative fixture를 점진적으로 추가한다.

capability별 확인 포인트:

- `cuda_pipeline_async`:
  async copy, stage commit/wait, barrier phase, staging lifetime 근거가 먼저 보이는지
- `cuda_thread_block_cluster`:
  cluster launch, `cluster.sync`, DSM ownership 근거가 먼저 보이는지
- `cuda_tma`:
  descriptor lifetime, bulk tensor copy completion, barrier phase 근거가 먼저 보이는지
- `cuda_wgmma`:
  warpgroup-uniform participation, issue/wait ownership, epilogue narrowing 근거가 먼저 보이는지

완료 기준:

- 새 CUDA capability가 들어와도 기존 최적화 루프에 별도 예외 없이 편입된다.
- capability별 profile miss, ranking drift, duplicate density를 운영 데이터로 바로 읽을 수 있다.
- capability 추가 이후에도 compact comment style과 mixed-language smoke가 유지된다.

## 권장 실행 순서

최적화는 아래 순서로 진행하는 것을 권장한다.

1. wrong-language telemetry 운영 루프 고도화
2. provider phrasing / draft quality 추가 튜닝
3. retrieval / ranking calibration 추가 보정
4. comment density / batch prioritization 최적화
5. mixed-language smoke / evaluation 강화
6. 운영 문서 / triage 기준 정리
7. CUDA capability expansion handoff optimization

이 순서를 권장하는 이유는 다음과 같다.

- 먼저 운영 데이터와 triage 기준을 고정해야 tuning 방향이 흔들리지 않는다.
- provider와 ranking을 먼저 만지면 comment density와 batch 품질도 함께 달라진다.
- smoke / evaluation 강화는 앞단 tuning 결과를 지속 검증하는 마지막 단계가 더 효율적이다.
- CUDA도 같은 원칙을 따르되, 새 CUDA 축 추가는 이 순서에 넣지 않고 별도 capability expansion으로 관리한다.
- 새 CUDA capability가 추가된 뒤의 tuning은 위 2-7단계에 그대로 흡수하고,
  capability 추가 자체는 별도 CUDA 계획 문서에서 먼저 닫는다.

## 검증 계획

최적화 단계에서 기본 검증은 아래를 유지한다.

- `cd review-engine && uv run pytest -q`
- `cd review-bot && uv run pytest -q`
- `cd review-platform && uv run pytest tests/test_pr_flow.py -q`
- `bash ops/scripts/smoke_local_gitlab_multilang_review.sh --json-output /tmp/review-bot-multilang-smoke.json`
- `python3 ops/scripts/build_wrong_language_backlog.py --project-ref <project> --window 28d --output <path>`

최적화별 추가 검증은 아래를 권장한다.

- provider tuning:
  language/profile/context별 representative fixture에서 comment phrasing snapshot 비교
- ranking tuning:
  golden example top-k contract와 false-positive regression 재확인
- telemetry tuning:
  wrong-language pair/path bucket backlog 생성과 triage 결과 점검
- density tuning:
  same-line/category suppression, file round-robin, batch cap 체감 점검
- CUDA tuning:
  `default`, `cuda_async_runtime`, `cuda_multigpu`, `cuda_tensor_core`, `cuda_cooperative_groups` 대표 fixture에서 top-k, phrasing, wrong-language, duplicate density를 함께 확인
- CUDA future-capability tuning:
  `cuda_pipeline_async`, `cuda_thread_block_cluster`, `cuda_tma`, `cuda_wgmma`가 구현되면 같은 checklist로 top-k, phrasing, wrong-language, duplicate density를 다시 확인

## 완료 정의

이 문서 기준 최적화 완료는 다음을 뜻한다.

- wrong-language telemetry가 운영 backlog로 안정적으로 연결된다.
- provider phrasing과 comment density가 눈에 띄게 더 일관된다.
- ranking drift가 언어별 regression으로 계속 제어된다.
- mixed-language smoke와 targeted regression이 운영 회귀를 빠르게 잡아낸다.
- 운영자가 detector / ranking / provider / UX 문제를 구분해 triage할 수 있다.
- 이미 구현된 CUDA 축도 위 완료 정의에 포함된다.
- 단, 새 CUDA 축 추가는 여전히 이 문서의 범위가 아니라 별도 capability expansion이다.
- 단, 새 CUDA 축이 추가된 뒤의 tuning, smoke, telemetry 흡수는 다시 이 문서의 범위로 들어온다.
