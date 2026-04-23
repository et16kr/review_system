# Review Engine Organization Rule System Design

- 문서 상태: Proposed Design
- 작성일: 2026-04-22
- 최종 갱신일: 2026-04-22
- 대상 독자: AI agent, 구현 담당자
- 관련 문서:
  - `docs/REVIEW_ENGINE_ORGANIZATION_RULE_SYSTEM_REQUIREMENTS.md`
  - `docs/REVIEW_ENGINE_RULE_MANAGEMENT_REQUIREMENTS.md`
  - `docs/REVIEW_ENGINE_MULTI_LANGUAGE_SUPPORT_REQUIREMENTS.md`
  - `docs/REVIEW_ENGINE_MULTI_LANGUAGE_RULE_ARCHITECTURE_DESIGN.md`

## 0. 이번 설계의 방향 고정

이 설계는 조직 전용 규칙 기능을 특정 회사 전용 기능으로 복원하지 않는다.
공개 코어에서 규칙의 우선권은 조직명이나 특정 내부 문서 존재 여부가 아니라
명시적인 `priority policy`로 표현한다.

이번 문서에서 고정하는 방향은 아래와 같다.

1. 공개 코어는 `organization rule pack`과 `priority policy`만 안다.
2. 조직 전용 guideline 문서 자체는 공개 계약에 포함하지 않는다.
3. 조직별 detector, prompt, pack 주입은 확장 지점으로만 제공한다.
4. 기존의 organization-specific override는 `priority tier`와 explicit override rule로 치환한다.

즉, 이전의 "특정 내부 규칙이 항상 이긴다"는 구조를 없애고,
"어떤 pack이 어떤 조건에서 더 높은 우선순위를 갖는가"를 설정으로 표현하는 것이 핵심이다.

## 1. 목적

이 문서는 `review-engine`의 organization rule system을
공개 코어와 private extension으로 분리 가능한 구조로 재설계하기 위한
구현 기준을 정의한다.

이번 설계의 목표는 아래 4가지다.

1. 공개 저장소에서 organization-specific rule coupling을 제거한다.
2. 규칙 우선권을 `authority` 하드코딩이 아니라 `priority policy`로 일반화한다.
3. private pack, detector, prompt overlay를 코어 수정 없이 다시 붙일 수 있게 한다.
4. public-only 설치와 private-extended 설치가 같은 ingest / retrieval / review 파이프라인을 공유하게 한다.

## 2. 현재 결합 지점 요약

현재 구현에는 organization-specific coupling이 여러 층에 남아 있다.

- [review-engine/review_engine/models.py](/home/et16/work/review_system/review-engine/review_engine/models.py:1)
  - `source_family`가 사실상 두 값에 고정되어 있다.
  - `authority`가 provenance가 아니라 precedence 역할까지 같이 맡고 있다.
- [review-engine/review_engine/config.py](/home/et16/work/review_system/review-engine/review_engine/config.py:1)
  - 특정 입력 파일과 산출물 이름이 기본값으로 박혀 있다.
- [review-engine/review_engine/ingest/build_records.py](/home/et16/work/review_system/review-engine/review_engine/ingest/build_records.py:1)
  - record 생성 시 precedence 계산이 특정 `source_family` 전제에 묶여 있다.
- legacy conflict resolver
  - 특정 family를 무조건 `authoritative`로 취급하던 분기는 제거 대상이었다.
  - 현재 구현에서는 별도 legacy resolver 모듈 대신 rule pack policy resolution 단계에서 처리한다.
- [review-engine/review_engine/retrieve/rerank.py](/home/et16/work/review_system/review-engine/review_engine/retrieve/rerank.py:1)
  - rerank score가 family 기반 authority score에 의존한다.
- [review-bot/review_bot/providers/openai_provider.py](/home/et16/work/review_system/review-bot/review_bot/providers/openai_provider.py:1)
  - provider prompt가 특정 조직/코드베이스 전제를 직접 포함한다.

이 상태에서는 public build와 private extension의 경계가 모호하고,
새 조직을 붙일 때마다 코어 코드 수정이 발생한다.

## 3. 목표 상태

목표 구조는 아래 한 문장으로 정리할 수 있다.

"공개 코어는 pack schema, priority policy, plugin interface만 제공하고,
조직별 특화는 외부 root 또는 package로 주입한다."

완료 후 기대 상태는 아래와 같다.

1. 규칙 source metadata는 provenance 표현에만 쓰고 precedence는 `priority policy`가 결정한다.
2. public pack만으로 ingest / retrieval / review가 완전 동작한다.
3. extension pack이 있으면 같은 파이프라인에 병합된다.
4. detector와 prompt overlay는 optional plugin으로 로드된다.
5. public CI는 private fixture 없이 통과하고, private CI는 extension만 추가해 확장 검증한다.

## 4. 설계 원칙

1. provenance와 precedence를 분리한다.
2. public core는 특정 조직명, 특정 내부 용어, 특정 private guideline 문서를 몰라야 한다.
3. 우선순위는 하드코딩이 아니라 policy file로 표현한다.
4. extension이 없어도 동작하는 경로를 기본 경로로 본다.
5. 기존 API와 테스트는 단계적으로 호환성을 유지하며 이동한다.
6. detector와 prompt specialization도 rule pack과 같은 방식으로 "발견 가능한 확장"으로 다룬다.

## 5. 상위 아키텍처

```text
public rule roots
  -> manifest / pack / profile loader
optional extension roots
  -> manifest / pack / profile loader
  -> detector plugins
  -> prompt overlays

merged rule registry
  -> priority policy resolver
  -> normalized guideline records
  -> active/reference/excluded datasets
  -> Chroma collections

review request
  -> language/profile selection
  -> public detector + optional extension detector
  -> retrieval/rerank using resolved priority score
  -> public prompt + overlay composition
  -> review result
```

여기서 중요한 점은
pack loading, detector loading, prompt loading이 모두 같은 `profile` 선택 결과를 공유한다는 것이다.
그래야 "같은 조직 정책을 쓰는데 retrieval은 일반 규칙, prompt는 조직 특화"처럼 서로 어긋나는 현상을 막을 수 있다.

## 6. Public Core 와 Private Extension 경계

| 영역 | public core 책임 | private extension 책임 | 비고 |
| --- | --- | --- | --- |
| canonical schema | pack/profile/policy schema 정의 | schema를 따르는 실제 pack 제공 | 코어는 schema만 소유 |
| public packs | 공개 표준 guideline pack 제공 | 없음 또는 optional overlay | public-only 설치의 기본값 |
| organization packs | loader, validator, merger 제공 | 실제 조직 규칙 pack 제공 | 외부 root 또는 package |
| priority policy | policy schema, merge 규칙, resolver 제공 | 조직별 우선순위 정책 제공 | precedence의 유일한 source |
| detector plugin | interface, discovery, fallback 제공 | 실제 조직 detector 구현 | 실패 시 public detector로 fallback |
| prompt overlay | overlay schema, composition order 제공 | 실제 조직 overlay 제공 | overlay 없음이 정상 경로 |
| CI | public-only validate/test | private extension validate/test | 서로 fixture를 공유하지 않음 |

경계 원칙은 단순하다.

- public core는 "확장 가능 구조"만 가진다.
- private extension은 "특화 내용"만 가진다.
- 둘 다 같은 runtime contract를 공유한다.

## 7. Canonical Schema

### 7.1 핵심 엔터티

이번 설계에서 규칙 관련 canonical schema는 아래 4개다.

1. `RulePackManifest`
2. `RuleEntry`
3. `ProfileConfig`
4. `PriorityPolicy`

### 7.2 `RulePackManifest`

pack 단위 메타데이터를 정의한다.

권장 필드:

- `schema_version`
- `pack_id`
- `namespace`
- `language_id`
- `source_kind`
- `description`
- `default_enabled`
- `default_priority_tier`
- `profile_tags`
- `plugin_refs`

여기서 핵심 필드는 아래와 같다.

- `pack_id`
  - 예: `cpp_core`, `shared_security`, `project_cpp`
- `namespace`
  - 예: `public`, `organization`, `project`
- `source_kind`
  - 예: `public_standard`, `organization_policy`, `project_policy`, `reference_import`

중요:

- `authority`는 manifest의 1차 필드가 아니다.
- precedence는 pack의 출처가 아니라 `PriorityPolicy`가 결정한다.

### 7.3 `RuleEntry`

개별 규칙은 아래 성격의 메타데이터를 가진다.

- 식별:
  - `rule_id`
  - `rule_no`
  - `pack_id`
  - `language_id`
- 본문:
  - `title`
  - `summary`
  - `text`
  - `keywords`
- review 메타:
  - `category`
  - `reviewability`
  - `fix_guidance`
  - `trigger_patterns`
- priority 메타:
  - `base_score`
  - `priority_tier`
  - `specificity`
  - `stability`
- conflict 메타:
  - `default_action`
  - `overrides`
  - `excluded_by`
  - `rationale`

`priority_tier` 권장 기본값은 아래와 같다.

- `reference`
- `default`
- `high`
- `override`

이 필드는 "어느 조직 규칙인가"가 아니라
"이 규칙이 selection과 충돌 해결에서 어느 정도 우선권을 갖는가"를 뜻한다.

### 7.4 `ProfileConfig`

profile은 어떤 pack 조합과 overlay 조합을 사용할지 결정한다.

최소 필드:

- `profile_id`
- `language_id`
- `enabled_packs`
- `shared_packs`
- `prompt_overlay_refs`
- `detector_refs`
- `priority_policy_ref`

profile은 다국어 설계 문서에서 말한 language/profile 구조를 그대로 재사용한다.
organization rule system은 새로운 축이 아니라 기존 profile 구조 위에 올라탄다.

### 7.5 `PriorityPolicy`

이 문서의 핵심 엔터티다.

`PriorityPolicy`는 아래를 정의한다.

- pack별 tier 기본값
- pack별 weight
- explicit override
- exclusion rule
- tie-breaker order
- compatible merge rule

예시 YAML:

```yaml
schema_version: 1
policy_id: cpp_default
language_id: cpp
tier_order:
  - override
  - high
  - default
  - reference
pack_weights:
  shared_security: 0.95
  cpp_core: 0.72
  project_cpp: 0.88
defaults:
  conflict_action: compatible
tie_breakers:
  - explicit_override
  - higher_tier
  - higher_specificity
  - higher_base_score
  - lexical_rule_id
overrides:
  - match:
      rule_id: cpp_core:NL.5
    action: overridden
    overridden_by:
      - project_cpp:NAMING-001
    rationale: "Project naming policy is intentionally narrower."
exclusions:
  - match:
      rule_id: cpp_core:LEGACY-001
    rationale: "Not applicable to current build target."
```

### 7.6 `authority`의 새 의미

기존 `authority`는 precedence를 결정하는 핵심 값이었다.
이번 설계에서는 이를 provenance tag로 축소한다.

권장 값:

- `standard`
- `organization`
- `project`
- `reference_import`

즉:

- `authority`는 "어디서 왔는가"
- `priority_tier`와 `pack_weights`는 "얼마나 우선하는가"

이렇게 역할을 분리한다.

## 8. Directory Layout 과 Loading 방식

### 8.1 Public Root

public root는 저장소 내부 canonical source다.

권장 구조:

```text
rules/
  shared/
    manifest.yaml
    packs/
    profiles/
    policies/
  cpp/
    manifest.yaml
    packs/
    profiles/
    policies/
  python/
    manifest.yaml
    packs/
    profiles/
    policies/
```

### 8.2 Extension Root

extension root는 public root와 같은 구조를 따른다.
차이는 배포 위치뿐이다.

지원 방식은 두 가지를 권장한다.

1. filesystem root
   - `REVIEW_ENGINE_EXTENSION_RULE_ROOTS=/opt/review-engine/rules:/workspace/private-rules`
2. package entry point
   - 예: `review_engine.rule_extensions`

### 8.3 Loader 절차

rule loader는 아래 순서로 동작한다.

1. public root manifest를 로드한다.
2. 설정된 extension root를 발견한다.
3. 모든 root에 대해 schema validation을 실행한다.
4. language/profile 선택에 필요한 manifest index를 만든다.
5. 선택된 profile의 `enabled_packs`, `shared_packs`, `priority_policy_ref`를 계산한다.
6. pack 내용을 합쳐 normalized `GuidelineRecord`로 변환한다.
7. priority policy resolver를 적용해 active/reference/excluded 집합을 만든다.
8. dataset JSON과 Chroma collection을 rebuild한다.

### 8.4 Loader 실패 정책

extension은 optional이므로 실패 정책을 명확히 해야 한다.

- public root validation 실패
  - startup/ingest 실패
- extension root validation 실패
  - 기본은 startup/ingest 실패
  - 단, `strict_extension_loading=false`일 때는 경고 후 해당 extension만 비활성화 가능
- detector/prompt plugin import 실패
  - 경고 로그 남기고 public fallback 사용

공개 제품의 기본값은 "extension이 없어도 정상 동작"이지,
"깨진 extension을 조용히 무시"가 아니다.
따라서 rule data 자체가 잘못되면 fail-fast가 맞다.

## 9. Priority Rule 설계

### 9.1 왜 `authority-first`를 버리는가

기존 구조는 사실상 아래 규칙을 전제한다.

- 특정 family면 우선
- 아니면 외부 규칙

이 방식은 다음 문제가 있다.

1. precedence가 provenance와 섞인다.
2. 한 조직 안에서도 pack별 세밀한 우선권을 표현하기 어렵다.
3. public guideline끼리도 안전성 pack, style pack, project pack의 우선순위를 구분하기 어렵다.

따라서 새 설계는 `authority-first` 대신 `priority-rule-first`를 사용한다.

### 9.2 우선순위 계산

최종 precedence 판단에는 아래 입력을 사용한다.

- `priority_tier`
- `pack_weight`
- `base_score`
- `specificity`
- explicit override rule

권장 계산 순서는 아래와 같다.

1. explicit override 존재 여부
2. higher `priority_tier`
3. higher `specificity`
4. higher `base_score`
5. higher `pack_weight`
6. stable lexical tie-breaker

retrieval rerank용 `resolved_priority_score`는 아래처럼 계산한다.

```text
resolved_priority_score =
  similarity_score * 0.45 +
  pack_weight * 0.20 +
  base_score * 0.20 +
  severity_default * 0.10 +
  pattern_boost * 0.05
```

여기서 기존 `authority_score`는 제거하고 `pack_weight`로 대체한다.

### 9.3 conflict action

저장 시점과 retrieval 시점에서 공통으로 쓰는 conflict action은 아래를 권장한다.

- `compatible`
- `overridden`
- `excluded`
- `reference_only`

기존 `authoritative`는 canonical stored state에서 제거한다.
호환성 계층에서는 아래처럼만 해석한다.

- legacy `authoritative` -> `priority_tier=override` + `conflict_action=compatible`

즉 "authoritative라는 이름의 특권 상태"가 아니라
"우선순위 tier가 높아 다른 규칙을 override할 수 있는 상태"로 바꾼다.

### 9.4 explicit override 와 exclusion

explicit override는 여전히 필요하다.
다만 기준이 특정 조직명이어서는 안 된다.

override rule은 아래 두 경우에만 사용한다.

1. 범용 규칙보다 더 좁고 명시적인 project/organization policy가 있을 때
2. 특정 guideline이 현재 제품/환경에 적용되지 않을 때

즉, override의 이유는 "누가 작성했는가"가 아니라
"어느 규칙이 더 좁고 더 직접적으로 적용되는가"가 되어야 한다.

## 10. Detector Plugin 인터페이스

### 10.1 목표

organization-specific detector는 public detector를 대체하는 것이 아니라
public detector 뒤에 추가로 붙는 plugin이어야 한다.

### 10.2 권장 인터페이스

```python
class QueryDetectorPlugin(Protocol):
    plugin_id: str

    def supports(self, *, language_id: str, profile_id: str | None) -> bool: ...

    def analyze(
        self,
        *,
        file_path: str | None,
        file_context: str | None,
        diff: str | None,
        code: str | None,
    ) -> list[QueryPattern]: ...
```

반환값은 기존 `QueryPattern`을 재사용한다.
plugin이 특정 private rule ID를 바로 반환하게 두기보다,
아래 중 하나를 반환하도록 제한하는 것이 좋다.

- `pattern name`
- `pattern evidence`
- `pack/tag hint`

그래야 public core가 private rule id 체계를 몰라도 된다.

### 10.3 실행 순서

권장 순서는 아래와 같다.

1. public language detector 실행
2. extension detector 실행
3. pattern dedupe
4. hinted pack/tag 계산
5. retrieval query 생성

### 10.4 실패 격리

detector plugin 예외는 리뷰 전체 실패로 번지지 않게 한다.

- detector 예외
  - warning log
  - 해당 plugin 결과만 폐기
  - public detector 결과로 계속 진행

이 정책은 prompt overlay보다 detector에서 더 중요하다.
query 분석 실패는 review quality는 낮출 수 있지만 availability를 깨면 안 되기 때문이다.

## 11. Provider Prompt Overlay 구조

### 11.1 현재 문제

현재 provider prompt는 특정 조직 코드베이스 관점이 문자열 상수로 직접 박혀 있다.
이 구조는 public build에서 제거되어야 한다.

### 11.2 목표 구조

prompt는 아래 4층으로 합성한다.

1. public base prompt
2. language prompt overlay
3. profile prompt overlay
4. optional extension prompt overlay

합성 순서는 고정하고,
각 층은 서로의 존재를 가정하지 않아야 한다.

### 11.3 prompt asset 예시

```text
prompts/
  base/system.md
  languages/cpp.md
  languages/python.md
  profiles/default.md
  profiles/security_strict.md
```

extension package는 같은 구조를 가질 수 있다.

```text
private_prompts/
  profiles/project_cpp.md
  overlays/release_branch.md
```

### 11.4 runtime 조합 규칙

`PromptComposer`는 아래 순서로 조합한다.

1. `base/system.md`
2. `languages/{language_id}.md`
3. `profiles/{profile_id}.md`
4. extension overlay refs

결과 prompt는 provider 직전에 완성하고,
provider 자체는 더 이상 특정 조직을 모르는 단순 consumer가 된다.

## 12. Ingest / Retrieval / Runtime 반영 방식

### 12.1 `models.py`

아래 방향으로 이동한다.

- `source_family` -> `pack_id` + `source_kind`
- `authority` -> provenance tag
- `priority` -> `base_score`
- `conflict_policy` -> `conflict_action`
- 추가:
  - `priority_tier`
  - `pack_weight`
  - `specificity`
  - `namespace`
  - `language_id`

단기 호환성을 위해 API/DB 경계에서는 alias를 유지할 수 있다.

- `source_family`는 임시로 `pack_id` alias
- `authority`는 optional legacy field

### 12.2 `config.py`

설정은 파일명을 직접 박는 방식에서 root 기반 discovery로 바꾼다.

권장 추가 필드:

- `public_rule_root`
- `extension_rule_roots`
- `default_profile_id`
- `strict_extension_loading`
- `prompt_root`
- `extension_prompt_roots`

### 12.3 `build_records.py`

현재의 단일 파이프라인을 아래 단계로 쪼갠다.

1. root discovery
2. manifest validation
3. pack parsing
4. priority policy resolution
5. normalized record build
6. dataset export

이때 `base_score` 계산과 `priority_tier` 결정은 분리해야 한다.

- `base_score`
  - rule text/keywords/category 기반 intrinsic score
- `priority_tier`
  - profile/policy 기반 precedence score

### 12.4 Priority policy resolution

`if source_family == ...` 분기를 제거하고,
`PriorityPolicy`가 계산한 action만 처리한다.

resolver 입력은 아래 정도면 충분하다.

- normalized records
- selected profile
- selected priority policy

### 12.5 `rerank.py`

`authority_score`를 없애고 `pack_weight`와 `resolved_priority_score`를 사용한다.

핵심은 아래 두 가지다.

1. "어느 조직 규칙인가"를 점수에 직접 반영하지 않는다.
2. "이 profile에서 더 우선해야 하는 pack인가"만 점수에 반영한다.

## 13. Public CI 와 Private CI 분리

### 13.1 Public CI

public CI는 아래만 검증한다.

1. public pack schema validation
2. public-only ingest
3. public detector/prompt fallback
4. public dataset golden test
5. 조직 전용 문자열/fixture가 core 경로에 남지 않았는지 확인

### 13.2 Private CI

private CI는 public CI 위에 아래를 더한다.

1. extension root validation
2. extension detector/prompt load test
3. merged profile ingest
4. organization-specific regression suite

### 13.3 로컬 전이 기간 테스트

마이그레이션 동안은 legacy guideline input을 로컬 fixture로 사용할 수 있다.
다만 아래 원칙을 둔다.

1. public schema의 canonical source로 취급하지 않는다.
2. public CI 필수 입력으로 넣지 않는다.
3. 저장소에 커밋해야 하는 파일로 간주하지 않는다.

즉, legacy input은 "전이 검증용 로컬 입력"일 뿐
"공개 코어의 기준 문서"가 아니다.

## 14. Migration Plan

### Phase 0. Compatibility Layer 도입

목표:

- 새 schema와 옛 runtime을 동시에 유지할 수 있는 얇은 변환 계층을 둔다.

작업:

1. `pack_id`, `source_kind`, `priority_tier`, `pack_weight` 필드 추가
2. `source_family`와 `authority`를 alias/derived field로 강등
3. 기존 dataset reader가 새 필드를 무시해도 깨지지 않게 한다

### Phase 1. Root / Manifest Loader 도입

목표:

- 단일 파일 경로 기반 ingest를 root 기반 ingest로 전환한다.

작업:

1. `rules/` canonical root 추가
2. manifest/profile/policy validator 추가
3. public-only ingest path 먼저 성공시킨다

### Phase 2. Priority Policy Resolver 도입

목표:

- precedence를 `source_family` 분기에서 policy 기반으로 옮긴다.

작업:

1. legacy authority score JSON 의미를 `priority_policy`로 치환
2. legacy conflict mapping JSON을 pack-neutral override schema로 변환
3. legacy conflict resolver의 family 하드코딩 제거
4. `rerank.py`에서 `authority_score` 제거

### Phase 3. Detector / Prompt Externalization

목표:

- 조직 특화 detector와 prompt를 runtime extension으로 이동한다.

작업:

1. query detector plugin interface 추가
2. prompt composer 도입
3. provider에서 조직 특화 문자열 상수 제거

### Phase 4. Public/Private Packaging 분리

목표:

- public 배포와 private 배포를 같은 코어 위에서 분리한다.

작업:

1. extension root env/entry point discovery 추가
2. public CI / private CI 파이프라인 분리
3. 문서와 운영 가이드를 public/private 경계 기준으로 업데이트

### Phase 5. Legacy Field 정리

목표:

- `source_family` 중심 사고를 걷어내고 새 schema를 기준으로 고정한다.

작업:

1. API 응답의 legacy alias 축소
2. 테스트 fixture를 `pack_id` 기준으로 교체
3. 저장 구조와 문서를 priority-rule-first 용어로 통일

## 15. 구현 우선순위

실행 순서는 아래를 권장한다.

1. schema / loader / policy parser
2. priority resolver
3. ingest export format
4. retrieval rerank
5. prompt composer
6. detector plugin
7. CI split

이 순서가 중요한 이유는
retrieval과 prompt를 먼저 바꾸면 입력 schema가 아직 고정되지 않아 다시 되돌아가기 쉽기 때문이다.

## 16. 열어둘 질문

아래는 구현 전에 한 번 더 결정이 필요한 항목이다.

1. `pack_weight`를 profile별로만 둘지, runtime feature flag로도 조정할지
2. `reference_only`를 conflict action으로 둘지, reviewability로만 표현할지
3. API/DB에서 `source_family` legacy alias를 언제 제거할지
4. extension loading 실패를 운영 환경에서 fail-fast로 강제할지

## 17. 최종 요약

이번 설계의 핵심은 아래 두 문장으로 요약된다.

1. organization rule system의 본질은 "특정 조직 규칙"이 아니라 "확장 가능한 pack + priority policy 구조"다.
2. precedence는 더 이상 `authority`나 조직 identity로 결정하지 않고, profile이 선택한 `priority policy`로 결정한다.

이 기준을 따르면 public core는 깔끔해지고,
private extension은 코어 수정 없이 다시 붙일 수 있으며,
향후 다국어 rule management 설계와도 자연스럽게 합쳐진다.
