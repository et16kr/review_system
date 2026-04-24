# Deferred Rule Authoring And Editor Work

## Purpose

이 문서는 rule lifecycle CLI, 수동 rule authoring UX, editor/UI처럼
rule 운영 자체를 더 편하게 만드는 deferred 작업을 모아 둔다.

마지막 코드 상태 점검일: `2026-04-24`

## 1. Manual Rule Editor / Authoring UX

현재 미루는 이유:

- canonical YAML과 Git history를 기준으로 수동 편집하는 토대는 이미 있다.
- 하지만 별도 editor/UI를 넣으려면 rule state model, validation, public/private extension 경계를 먼저 굳혀야 한다.
- 지금은 editor보다 rule gap closure와 운영 품질 유지가 더 직접적인 가치가 크다.

착수 전 선행 조건:

1. rule lifecycle CLI의 최소 범위를 먼저 정한다.
2. canonical YAML schema, profile/policy merge, extension boundary를 명확히 유지한다.
3. UI가 별도 저장 모델을 만들지 않도록 운영 원칙을 먼저 고정한다.
4. canonical YAML authoring model이 unknown key를 silent ignore하지 않도록 fail-fast guardrail을 둔다.
5. missing/duplicate selected pack과 default profile selection 의미를 먼저 정리한다.

readiness packet:

- 기존 `python -m review_engine.cli.rule_lifecycle` write boundary는 좁게 유지한다.
  - `list`/`show`는 generated dataset이나 vector store를 읽지 않는 read-only inspection이다.
  - `disable`/`enable`은 single canonical pack YAML entry의 `enabled` field만 수정한다.
  - `disable-pack`/`enable-pack`은 single canonical profile YAML의 `enabled_packs` 또는
    `shared_packs`만 수정한다.
  - selected runtime이 여러 profile YAML merge 결과면 single write boundary를 잃으므로
    mutation은 fail-fast 한다.
- future editor가 새로 다룰 surface는 CLI가 이미 수정하는 boolean toggle이 아니라 아래로 제한한다.
  - canonical rule entry 초안 작성과 기존 entry metadata 편집
  - profile pack membership preview와 policy impact preview
  - source coverage atom 연결 상태, strict YAML validation, ingest/retrieval 영향 preview
  - lifecycle CLI가 출력하는 `validation_plan`과 release-gate command를 실행 또는 복사 가능한 형태로 노출
- authoring에서 자주 틀리는 metadata/validation failure 후보는 먼저 editor scope 후보로만 둔다.
  - typoed YAML key: `fix_guidence`, `enabled_packz` 같은 unknown field
  - `pack_id`와 legacy `source_family` 불일치
  - duplicate loaded `pack_id` 또는 explicit profile selection의 unknown pack id
  - `default_action`이나 policy defaults에서 runtime conflict state를 authoring field로 직접 쓰려는 경우
  - rule entry의 `reviewability`, `applies_to`, `false_positive_risk`, `priority_tier` literal mismatch
  - source manifest atom 누락 또는 canonical rule reverse coverage 누락
  - default profile fallback과 path/content inference 우선순위를 operator가 오해하는 경우
- editor는 canonical YAML과 Git history를 우회하지 않는다.
  - 별도 DB-backed rule state나 generated dataset patch를 source of truth로 만들지 않는다.
  - editor output은 canonical YAML diff와 validation result를 남기고, merge/review는 Git workflow가 소유한다.
  - generated JSON/vector artifacts는 ingest 산출물이며 사람이 직접 편집하는 대상이 아니다.
  - private/organization extension도 같은 canonical YAML schema와 validation gate를 통과해야 한다.

착수 후 해야 할 일:

1. readiness packet의 metadata/validation failure 후보를 editor form validation과 message 우선순위로 나눈다.
2. rule authoring form 또는 editor가 수정해야 할 canonical 파일 경로를 명확히 드러낸다.
3. preview, validate, ingest, regression 연결 방식을 설계한다.
4. 웹 UI를 붙이더라도 Git 기반 운영과 충돌하지 않도록 감사 경로를 유지한다.

## 2. Private Rule Packaging Readiness

현재 미루는 이유:

- filesystem extension root와 private extension runtime test는 있지만, 배포 가능한 package shape,
  version/compatibility metadata, install/update path는 아직 owner가 없다.
- private generated artifact와 public canonical artifact를 섞으면 review reproducibility가 약해진다.
- packaging을 먼저 구현하면 schema strictness와 extension boundary가 흔들릴 수 있다.

착수 전 선행 조건:

1. canonical YAML unknown key rejection과 pack/profile fail-fast guardrail을 먼저 닫는다.
2. package manifest가 포함해야 할 최소 metadata를 정한다.
   - package id
   - version
   - compatible engine schema/runtime version
   - included packs/profiles/policies/source manifests
3. private generated artifact를 repo canonical artifact와 분리하는 위치와 naming rule을 정한다.
4. install/update/rollback 절차와 validation gate를 정한다.

착수 후 해야 할 일:

1. `review-engine/examples/extensions/private_org_cpp/` 수준의 filesystem extension을
   installable package shape로 승격할지 결정한다.
2. package validation CLI 또는 existing ingest validation 확장 지점을 정한다.
3. private package가 runtime retrieval, source coverage, lifecycle CLI와 충돌하지 않는지
   deterministic test를 추가한다.
