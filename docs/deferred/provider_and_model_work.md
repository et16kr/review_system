# Deferred Provider And Model Work

## Purpose

이 문서는 provider backend, model backend, ranking/density tuning처럼
LLM 경로와 직접 연결된 deferred 작업을 모아 둔다.

마지막 코드 상태 점검일: `2026-04-24`

## 1. Provider / Ranking / Density Tuning

현재 미루는 이유:

- direct OpenAI provider path가 현재 환경에서 `insufficient_quota`로 막혀 있다.
- fallback lifecycle smoke 통과만으로는 provider-direct artifact를 재수집한 것으로 볼 수 없다.
- human review가 필요한 단계가 포함되어 있어 완전 자동화에 맞지 않는다.
- provider provenance observability와 config fail-fast 같은 runtime guardrail은 별도 선행 작업으로 먼저 다루는 편이 안전하다.

착수 전 선행 조건:

1. quota/billing이 정상인 OpenAI API 환경을 준비한다.
2. direct OpenAI smoke가 실제 live provider call에서 성공하는지 확인한다.
3. OpenAI comparison artifact를 재수집할 수 있는 사람 검토 시간을 확보한다.
4. lifecycle provider runtime에서 configured/effective provider뿐 아니라 model, endpoint,
   transport provenance가 API, log, summary note에 남는지 확인한다.
5. direct smoke preflight가 timeout 없이 automation loop를 멈출 수 없도록 bounded runtime을
   먼저 적용한다.
6. default OpenAI artifact와 OpenAI-compatible local backend artifact가 filename,
   env contract, embedded provenance에서 섞이지 않도록 retained capture 규칙을 고정한다.

착수 후 해야 할 일:

1. 실제 OpenAI comparison artifact를 재수집한다.
2. OpenAI와 `stub` 결과의 title/summary/fix guidance 길이, claim strength, evidence anchoring을 사람이 검토한다.
3. `prompt_tune`, `ranking_tune`, `rule_gap`, `defer` 판정을 decision artifact에 남긴다.
4. ranking weight가 바뀌면 deterministic regression을 먼저 추가하고 baseline diff로 설명 가능하게 만든다.
5. project-local feedback이 필요하면 전역 `rule_no` weight와 분리 설계를 만든다.

## Readiness Packet

direct OpenAI smoke 성공 판정은 한 줄로 고정한다:
default OpenAI artifact는 default base URL에서 `--expect-live-openai`로 실행해 exit `0`,
`models_probe_status=ok`, `live_probe_model=...`을 모두 남긴 경우에만 provider-direct
success evidence다. fallback이 켜진 lifecycle smoke 통과, `OPENAI_API_KEY` 누락으로 인한
skipped artifact, `insufficient_quota`, timeout, local backend artifact는 default OpenAI tuning
근거가 아니다.

human comparison checklist:

1. artifact provenance를 먼저 확인한다.
   - `stub_provider_runtime.transport_class=deterministic_stub`
   - `openai_provider_runtime.endpoint_base_url=https://api.openai.com/v1`
   - `openai_provider_runtime.configured_model`이 의도한 모델이다.
   - `openai_provider_runtime.transport_class=default_openai_base_url`
2. comparison artifact의 `openai_status`, `human_review_required`,
   `recommended_next_action`, `case_deltas`를 기록한다.
3. 사람이 각 comparable case에서 아래 축을 확인한다.
   - groundedness: snippet에 없는 사실을 만들지 않는다.
   - evidence_anchoring: title/summary가 line evidence와 연결된다.
   - claim_strength: 불확실한 위험을 과장하지 않는다.
   - specificity: language/profile/context 정보를 유지한다.
   - actionability: suggested fix가 실제 수정 행동으로 이어진다.
   - brevity: review UI에서 과하게 길지 않다.
   - noise_risk: 중복/상투 표현으로 publish noise를 만들지 않는다.
4. decision artifact는 case별로 `accept_baseline`, `prompt_tune`, `ranking_tune`,
   `rule_gap`, `defer` 중 하나만 기록한다.
5. `prompt_tune`이나 `ranking_tune`을 고르려면 먼저 해당 case를 재현하는 deterministic
   regression 또는 명시적 baseline diff 설명을 만든다.

quota/billing 정상 환경에서 재수집 순서:

1. 같은 UTC 날짜와 branch/commit을 기준으로 output filename을 정한다.
2. deterministic `stub` provider quality artifact와 JSON을 먼저 재수집한다.
3. default OpenAI direct smoke를 `--expect-live-openai`로 실행하고 retained stdout을 남긴다.
4. direct smoke가 위 success gate를 만족하지 않으면 멈추고 `defer` decision artifact만 남긴다.
5. default OpenAI provider quality artifact와 JSON을 재수집한다.
6. stub/OpenAI provider comparison artifact와 JSON을 만든다.
7. 사람이 comparison checklist를 적용해 `provider_review_decisions_YYYY-MM-DD.md`를 남긴다.
8. decision artifact가 `prompt_tune`, `ranking_tune`, `rule_gap`을 명시한 case만 후속 roadmap
   unit으로 승격한다.
9. ranking/density 변경 전에는 `provider_ranking_density_YYYY-MM-DD.md` 또는 equivalent
   deterministic density baseline을 먼저 남긴다.

## Post-Review Boundary

`2026-04-24` 리뷰 라운드 기준으로 provider/ranking/density tuning 자체는 여전히 deferred다.
OpenAI quota, live direct-provider evidence, human comparison review가 필요하기 때문이다.

반대로 아래 항목은 provider tuning이 아니라 즉시 수정할 runtime guardrail이다.

- lifecycle `provider_runtime`에 model/base URL/transport provenance 추가
- OpenAI direct smoke preflight에 connect/overall timeout 추가
- local backend retained artifact env/provenance/filename contract 정리
- `ROADMAP.md`에서 닫힌 provider 기반과 아직 남은 provenance work를 분리

따라서 provider tuning을 시작하기 전에 위 guardrail을 먼저 닫고, 그 뒤 live provider artifact를
새로 수집한다.
