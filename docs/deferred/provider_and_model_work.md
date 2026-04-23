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

착수 후 해야 할 일:

1. 실제 OpenAI comparison artifact를 재수집한다.
2. OpenAI와 `stub` 결과의 title/summary/fix guidance 길이, claim strength, evidence anchoring을 사람이 검토한다.
3. `prompt_tune`, `ranking_tune`, `rule_gap`, `defer` 판정을 decision artifact에 남긴다.
4. ranking weight가 바뀌면 deterministic regression을 먼저 추가하고 baseline diff로 설명 가능하게 만든다.
5. project-local feedback이 필요하면 전역 `rule_no` weight와 분리 설계를 만든다.

## 2. OpenAI-Compatible Local LLM Backend

현재 미루는 이유:

- 현재 `review-bot` provider는 사실상 `openai`와 `stub`만 지원한다.
- local LLM을 붙이려면 provider 계층 확장과 품질/운영 기준이 먼저 필요하다.
- OpenAI API blocker와는 별개로, local backend는 별도 품질/latency/structured output 검토가 필요하다.

권장 방향:

- `openai`를 완전히 대체하는 별도 provider보다,
  OpenAI-compatible backend 계층을 두고
  OpenAI API와 local OpenAI-compatible endpoint를 같은 추상화 아래에서 선택 가능하게 만든다.

착수 전 선행 조건:

1. OpenAI-compatible endpoint 전략을 고른다.
   - 예: `Ollama`, `LM Studio`, `vLLM`
2. structured output / schema adherence / 한국어 리뷰 품질 기준을 정한다.
3. fallback 정책을 정한다.
   - local only
   - local -> stub
   - openai -> local -> stub
4. local backend의 latency/VRAM/throughput 운영 기준을 정한다.

착수 후 해야 할 일:

1. provider abstraction을 OpenAI-compatible backend를 받을 수 있게 확장한다.
2. endpoint/base URL/model 설정 경로를 추가한다.
3. local backend smoke와 provider quality baseline을 추가한다.
4. OpenAI API와 local backend를 같은 comparison artifact 체계 안에서 비교할지 결정한다.
