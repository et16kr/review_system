# Review Engine CUDA Native Capability Expansion Plan

## 목적

이 문서는 `review-engine` / `review-bot`의 CUDA 지원을
기존 baseline 축 바깥으로 넓히기 위한
**비최적화 capability expansion 작업만** 별도로 기록한다.

이 문서의 목적은 다음과 같다.

- CUDA 작업 중 "새 capability 추가"와 "이미 있는 축 최적화"를 분리한다.
- CUDA native feature 확장 범위를 library/ecosystem 확장과 분리한다.
- 각 capability를 source, canonical rule, detector, prompt, example, regression까지
  한 묶음으로 닫는 실행 단위를 고정한다.

이 문서는 후속 최적화 문서를 대체하지 않는다.
이미 구현된 CUDA 축과 앞으로 추가될 CUDA 축의 retrieval, phrasing, smoke,
telemetry 최적화는 계속
`docs/REVIEW_ENGINE_MULTI_LANGUAGE_FOLLOWUP_OPTIMIZATION_PLAN.md`
에서 관리한다.

## 문서 분리 원칙

현재 CUDA 작업은 아래 두 갈래로 나눈다.

1. capability expansion
- 새 `profile_id` / pack / source bundle / detector / prompt / example / regression을 추가하는 일
- 이 문서에서 관리한다

2. optimization
- ranking, phrasing, comment density, telemetry, mixed-language smoke를 다듬는 일
- 기존 멀티 랭귀지 최적화 문서에서 관리한다

즉 `cuda::pipeline`, `thread_block_cluster`, `TMA`, `wgmma`를
새로 지원하는 일은 이 문서의 범위이고,
그 축들이 들어온 뒤 top-k, provider phrasing, wrong-language,
smoke를 다듬는 일은 최적화 문서의 범위다.

## 현재 기준선

현재 runtime에 이미 연결된 CUDA 축은 다음과 같다.

- `cuda/default`
- `cuda_async_runtime`
- `cuda_multigpu`
- `cuda_tensor_core`
- `cuda_cooperative_groups`

즉 CUDA는 현재 baseline, async, multi-GPU, Tensor Core, Cooperative Groups까지
canonical source/rule/query/example/regression이 연결된 상태다.

이 문서가 다루는 것은
"이미 있는 축을 더 좋게 만드는 일"이 아니라
"아직 없는 CUDA native capability를 새 축으로 수용하는 일"이다.

## 진행 현황

2026-04-22 기준:

- 완료: `cuda_pipeline_async`
  - runtime profile inference
  - source bundle / canonical pack / prompt overlay
  - example / diff / safe regression fixture
  - engine / bot regression
- 완료: `cuda_thread_block_cluster`
  - runtime profile inference
  - source bundle / canonical pack / prompt overlay
  - example / diff / safe regression fixture
  - engine / bot regression
  - ingest 반영 (`cuda_thread_block_cluster: 5`)
- 완료: `cuda_tma`
  - runtime profile inference
  - source bundle / canonical pack / prompt overlay
  - example / diff / safe regression fixture
  - engine / bot regression
  - ingest 반영 (`cuda_tma: 5`)
- 완료: `cuda_wgmma`
  - runtime profile inference
  - source bundle / canonical pack / prompt overlay
  - example / diff / safe regression fixture
  - engine / bot regression
  - ingest 반영 (`cuda_wgmma: 5`)
- 남은 확장 phase:
  - 없음

## 범위

이 문서에 포함되는 것은 다음과 같다.

- 새 CUDA native capability에 대한 `profile_id` 정의
- 언어/프로필 registry inference 확장
- CUDA source bundle 추가
- canonical rule pack/profile/policy 연결
- query detector / hinted rule mapping 추가
- prompt overlay 추가
- example / diff / false-positive regression fixture 추가
- ingest / retrieval / bot propagation 회귀 추가

이 문서에 포함되지 않는 것은 다음과 같다.

- `cuBLAS`, `cuDNN`, `CUTLASS`, `Thrust` 같은 library-specific deepening
- `multi-node NCCL`, `NVSHMEM` 같은 분산/통신 ecosystem 확장
- ranking, phrasing, telemetry, smoke tuning 자체
- DB schema 변경
- 외부 API / CLI contract 변경

즉 이번 CUDA 확장은 "library support"보다
"CUDA 자체 execution / memory / synchronization model"을 더 깊게 지원하는 데 초점을 둔다.

## 구현 원칙

이번 CUDA capability expansion은 아래 원칙으로 고정한다.

### 1. Accuracy-first Hybrid

- 강한 신호와 수정 가이드가 있는 규칙은 `auto_review`로 넣는다.
- 문맥 의존성이 큰 항목은 `reference_only`로 넣는다.
- 새 capability를 넣더라도 generic 성능 코멘트가 상위권을 오염시키지 않게 한다.

### 2. Official-source summary only

- source bundle은 NVIDIA 공식 문서를 바탕으로 정규화 summary만 저장한다.
- 원문 전체를 runtime canonical rule로 복제하지 않는다.

### 3. Capability ships as a full slice

각 capability는 아래를 함께 갖춰야 "완료"로 본다.

- source bundle
- canonical pack/profile/policy
- query detector
- prompt overlay
- example + diff fixture
- regression test

즉 detector 없는 rule 묶음이나,
example/test 없이 source만 추가하는 방식은 이번 원칙에 맞지 않는다.

## 우선 확장 대상

CUDA native capability expansion은 아래 순서로 진행한다.

### Phase 1. `cuda_pipeline_async`

목표:
- `cuda::pipeline`, `memcpy_async`, `cp.async`, stage commit/wait,
  barrier-linked async copy를 reviewable profile로 수용한다.

추가할 내용:
- 새 profile: `cuda_pipeline_async`
- 새 pack: async copy staging, wait ownership, barrier phase parity,
  shared-memory staging lifetime, producer/consumer phase drift
- detector 신호:
  - `cuda::pipeline`
  - `memcpy_async`
  - `cp.async`
  - `producer_acquire`
  - `producer_commit`
  - `consumer_wait`
  - `cuda::barrier`
  - `mbarrier`
- prompt 초점:
  - async copy가 실제 completion boundary를 코드에서 드러내는지
  - pipeline stage ownership이 local patch에서 읽히는지
  - staging buffer lifetime이 producer/consumer phase와 맞는지

대표 rule 방향:
- async copy issue가 "복사 호출 존재"가 아니라
  "wait/arrival/phase ownership이 local code에서 끊겼는지"를 본다
- `cp.async` fast path는 단순 성능 코멘트보다
  barrier parity와 staged shared-memory lifetime을 먼저 본다

### Phase 2. `cuda_thread_block_cluster`

목표:
- thread block cluster, cluster-level sync, distributed shared memory를
  CUDA 자체 capability로 수용한다.

추가할 내용:
- 새 profile: `cuda_thread_block_cluster`
- 새 pack: cluster launch ownership, cluster sync collective safety,
  cluster-wide resource contract, distributed shared memory rank ownership
- detector 신호:
  - `__cluster_dims__`
  - `cluster_group`
  - `this_cluster`
  - `cluster.sync`
  - `map_shared_rank`
  - distributed shared memory 관련 토큰
- prompt 초점:
  - cluster launch contract가 launch site와 kernel body에 함께 보이는지
  - DSM access가 remote rank ownership을 분명히 드러내는지
  - cluster-wide collective가 partial participation 아래로 들어가지 않는지

대표 rule 방향:
- cluster 기능은 "고급 성능 기능"으로만 보지 않고
  collective participation과 remote shared-memory ownership 문제로 canonicalize한다

### Phase 3. `cuda_tma`

목표:
- Tensor Memory Accelerator 관련 bulk tensor copy와 descriptor/barrier contract를
  별도 CUDA capability로 수용한다.

추가할 내용:
- 새 profile: `cuda_tma`
- 새 pack: tensor map descriptor lifetime, bulk async tensor copy completion,
  barrier phase ownership, tensor shape/alignment contract visibility
- detector 신호:
  - `tma`
  - `tensormap`
  - `cp.async.bulk.tensor`
  - bulk tensor copy / barrier coupling 토큰
- prompt 초점:
  - tensor map descriptor가 누구 소유인지
  - bulk tensor copy completion이 어떤 barrier phase로 귀결되는지
  - shape/stride/alignment 계약이 helper 뒤로 숨지 않는지

대표 rule 방향:
- TMA는 "빠르다/느리다"보다
  descriptor + barrier + staging contract visibility를 먼저 본다

### Phase 4. `cuda_wgmma`

목표:
- Hopper 계열 warpgroup MMA 경로를
  WMMA/Tensor Core와 구분되는 CUDA native capability로 수용한다.

추가할 내용:
- 새 profile: `cuda_wgmma`
- 새 pack: warpgroup-uniform participation, shared staging contract,
  async MMA issue/wait ownership, epilogue narrowing boundary
- detector 신호:
  - `wgmma`
  - warpgroup MMA async instruction 토큰
  - warpgroup arrive/commit/wait 류 토큰
- prompt 초점:
  - warpgroup collective participation이 uniform한지
  - staged tile ownership과 wait boundary가 local code에서 보이는지
  - mixed-precision epilogue가 result contract를 숨기지 않는지

대표 rule 방향:
- `wgmma`는 generic tensor-core 성능 가이드가 아니라
  warpgroup collective correctness와 issue/wait ownership 문제로 다룬다

## 공통 구현 변경

각 phase에서 공통으로 필요한 변경은 다음과 같다.

### 1. Rule/source layer

- `review-engine/rule_sources/cuda/`에 capability별 source bundle 추가
- `review-engine/rules/cuda/`에 pack/profile 추가
- `manifest.yaml`, `coverage_matrix.yaml` 갱신

### 2. Registry/query layer

- `review_engine/languages/registry.py`
- `review-bot/review_bot/language_registry.py`
- `review_engine/query/languages/cuda.py`

위 3곳에서 새 profile inference와 detector-backed hinted rule mapping을 함께 늘린다.

### 3. Prompt layer

- `review-engine/prompts/profiles/`에 capability별 prompt overlay 추가
- provider prompt는 기존 compact comment style을 유지하되
  capability-specific evidence ordering만 보강한다

### 4. Example/regression layer

- `review-engine/examples/multilang/`
- `review-engine/examples/multilang_diffs/`
- `review-engine/examples/multilang_safe/`
- `review-engine/tests/`
- `review-bot/tests/`

각 capability마다 최소 다음을 갖춘다.

- positive code example
- diff example
- safe or false-positive regression example
- engine registry/query/retrieval regression
- bot payload propagation regression

## 권장 실행 순서

아래 순서를 권장한다.

1. `cuda_pipeline_async`
2. `cuda_thread_block_cluster`
3. `cuda_tma`
4. `cuda_wgmma`

이 순서를 권장하는 이유는 다음과 같다.

- `pipeline/cp.async`는 native async memory/synchronization 축이라 coverage 이득이 가장 넓다.
- cluster와 DSM은 cooperative groups보다 한 단계 더 넓은 collective contract로 이어지므로 두 번째가 자연스럽다.
- TMA는 descriptor/barrier coupling을 요구하므로 pipeline/cluster 축 이후가 구현하기 쉽다.
- `wgmma`는 architecture-specific nuance가 많아 앞선 async/staging contract를 정리한 뒤 들어가는 편이 안전하다.

## 검증 계획

각 phase 완료 시 아래 검증을 수행한다.

- `cd review-engine && uv run python -m review_engine.cli.ingest_guidelines`
- `cd review-engine && uv run pytest tests/test_language_registry.py tests/test_query_conversion.py tests/test_multilang_regressions.py tests/test_expected_examples.py tests/test_source_coverage_matrix.py -q`
- `cd review-engine && uv run pytest -q`
- `cd review-bot && uv run pytest tests/test_language_registry.py tests/test_review_runner.py -q`
- `cd review-bot && uv run pytest -q`
- `cd review-platform && uv run pytest tests/test_pr_flow.py -q`

phase별 추가 확인:

- new profile inference가 generic `cuda/default`로 떨어지지 않는지
- 새 capability direct detector hit가 generic CUDA rule보다 앞서는지
- `reference_only`가 inline defect claim 상위권을 오염시키지 않는지
- compact language tag가 계속 `[봇 리뷰][cuda]`를 유지하는지

## 완료 정의

이 문서 기준 CUDA capability expansion 완료는 다음을 뜻한다.

1. 각 신규 capability가 별도 `profile_id`로 runtime에 연결된다.
2. 각 capability에 대해 source bundle, canonical pack/profile, detector, prompt, example, regression이 모두 존재한다.
3. ingest 후 CUDA parsed/active/reference 수가 capability 증분을 반영한다.
4. engine과 bot 회귀가 새 capability를 포함한 상태로 통과한다.
5. 이후 tuning 과제는 더 이상 이 문서가 아니라
   `REVIEW_ENGINE_MULTI_LANGUAGE_FOLLOWUP_OPTIMIZATION_PLAN.md`
   로 넘길 수 있다.

## 비고

현재 사용자 의도 기준으로는
library deepening보다 CUDA 자체 capability deepening이 우선이다.

따라서 다음 CUDA 단계는 기본적으로 아래와 같이 본다.

- 우선: `cuda_pipeline_async`, `cuda_thread_block_cluster`, `cuda_tma`, `cuda_wgmma`
- 후순위: `CUTLASS`, `cuBLAS/cuDNN`, `multi-node NCCL`, `NVSHMEM`
