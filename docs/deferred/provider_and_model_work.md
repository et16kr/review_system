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

착수 후 해야 할 일:

1. 실제 OpenAI comparison artifact를 재수집한다.
2. OpenAI와 `stub` 결과의 title/summary/fix guidance 길이, claim strength, evidence anchoring을 사람이 검토한다.
3. `prompt_tune`, `ranking_tune`, `rule_gap`, `defer` 판정을 decision artifact에 남긴다.
4. ranking weight가 바뀌면 deterministic regression을 먼저 추가하고 baseline diff로 설명 가능하게 만든다.
5. project-local feedback이 필요하면 전역 `rule_no` weight와 분리 설계를 만든다.

## Post-Review Boundary

`2026-04-24` 리뷰 라운드 기준으로 provider/ranking/density tuning 자체는 여전히 deferred다.
OpenAI quota, live direct-provider evidence, human comparison review가 필요하기 때문이다.

반대로 아래 항목은 provider tuning이 아니라 즉시 수정할 runtime guardrail이다.

- lifecycle `provider_runtime`에 model/base URL/transport provenance 추가
- OpenAI direct smoke preflight에 connect/overall timeout 추가
- `ROADMAP.md`에서 닫힌 provider 기반과 아직 남은 provenance work를 분리

따라서 provider tuning을 시작하기 전에 위 guardrail을 먼저 닫고, 그 뒤 live provider artifact를
새로 수집한다.
