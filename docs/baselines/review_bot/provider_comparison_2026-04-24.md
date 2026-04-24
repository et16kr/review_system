# Review Bot Provider Comparison

- generated_at: `2026-04-24T13:34:56Z`
- corpus_revision: `packaged-provider-quality-cases`
- stub_status: `passed`
- openai_status: `failed`
- stub_provider_runtime: `configured_provider=stub, effective_provider=stub, fallback_used=False, transport_class=deterministic_stub`
- openai_provider_runtime: `configured_provider=openai, effective_provider=openai, fallback_used=False, configured_model=gpt-5.2, endpoint_base_url=https://api.openai.com/v1, transport_class=default_openai_base_url`
- case_count: `6`
- compared_case_count: `6`
- human_review_required: `True`
- recommended_next_action: `review_provider_deltas_before_tuning`

## Review Rubric

| Axis | Check |
| --- | --- |
| groundedness | Does the draft avoid facts missing from the snippet? |
| evidence_anchoring | Does title/summary connect to line evidence? |
| claim_strength | Does it avoid overclaiming uncertain risk? |
| specificity | Does it preserve language/profile/context details? |
| actionability | Is the suggested fix concrete enough to act on? |
| brevity | Is it concise enough for review UI? |
| noise_risk | Does it avoid duplicate/noisy phrasing? |

## Case Deltas

| case_id | recommendation | status | title_delta | summary_delta | fix_delta | required_delta | line_mismatch | publish_mismatch |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| cuda_async_default_stream | human_review | passed -> failed | 0 | 2 | 231 | 0 | False | False |
| cuda_cooperative_groups_grid_sync | human_review | passed -> failed | 0 | 113 | 399 | 0 | False | False |
| python_fastapi_blocking_io | human_review | passed -> failed | -8 | 10 | 327 | 1 | False | False |
| python_fastapi_untyped_request_body | human_review | passed -> failed | 0 | 48 | 659 | 0 | False | False |
| sql_ordinal_group_by | human_review | passed -> failed | 1 | 77 | 170 | 1 | False | False |
| yaml_ci_remote_script_execution | human_review | passed -> failed | 3 | 29 | 260 | 0 | False | False |

## Human Review Checklist

### cuda_async_default_stream

- recommendation: `human_review`
- signals: status mismatch, large suggested_fix length delta
- stub_title: CUDA stream 0 사용이 async 순서를 숨깁니다
- openai_title: cudaMemcpyAsync에 stream 0을 고정 사용

### cuda_cooperative_groups_grid_sync

- recommendation: `human_review`
- signals: status mismatch, large suggested_fix length delta
- stub_title: grid.sync()의 cooperative launch 계약을 드러내 주세요
- openai_title: grid.sync() 사용 전 cooperative launch 계약이 숨겨짐

### python_fastapi_blocking_io

- recommendation: `human_review`
- signals: status mismatch, required term coverage regression, large suggested_fix length delta
- stub_title: 비동기 핸들러 안에 blocking 작업이 섞이지 않게 해 주세요
- openai_title: async 핸들러에서 requests로 블로킹 호출

### python_fastapi_untyped_request_body

- recommendation: `human_review`
- signals: status mismatch, large suggested_fix length delta
- stub_title: 요청 본문을 타입 모델로 검증해 주세요
- openai_title: 요청 바디를 직접 파싱해 검증이 우회됨

### sql_ordinal_group_by

- recommendation: `human_review`
- signals: status mismatch, required term coverage regression, large suggested_fix length delta
- stub_title: GROUP BY 순번 지정은 변경에 취약합니다
- openai_title: GROUP BY 서수 사용으로 결과 계약 불안정

### yaml_ci_remote_script_execution

- recommendation: `human_review`
- signals: status mismatch, large suggested_fix length delta
- stub_title: CI에서 외부 스크립트를 검증 없이 실행하고 있습니다
- openai_title: 원격 스크립트 즉시 실행으로 provenance 검증 누락

## Tuning Guardrail

Do not change prompt or ranking weights from this artifact alone.
Use this summary to create a targeted regression or a separate tuning task first.

