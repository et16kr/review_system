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

readiness packet:

- installable private rule package는 runtime extension root와 package metadata를 분리한다.
  - 현재 runtime loader가 읽는 `manifest.yaml`은 계속 `pack_files`, `profile_files`,
    `policy_files`를 가리키는 rule-root manifest다.
  - future package boundary는 같은 root의 추가 `package.yaml` 또는 package wrapper manifest로
    표현하고, runtime `manifest.yaml`을 package metadata 저장소로 확장하지 않는다.
- package metadata의 최소 field는 아래로 고정한다.
  - `package_id`: organization/package identity. reverse-DNS 또는 slug 형식의 stable ASCII id를
    권장하며, `pack_id`와 같은 값으로 암묵 처리하지 않는다.
  - `package_version`: SemVer-compatible version. install/update/rollback과 generated artifact
    naming은 이 값을 기준으로 한다.
  - `package_kind`: v1은 `review_engine_rule_extension`만 허용한다.
  - `schema_version`: package manifest schema version. v1 첫 구현은 `1`만 허용한다.
  - `compatible_review_engine`: 최소 `rule_schema_version`과 optional
    `min_review_engine_version` / `max_review_engine_version` 또는 equivalent build identifier를
    포함한다.
  - `extension_roots`: package 안에서 runtime `manifest.yaml`을 가진 relative root 목록. v1은
    하나의 rule root만 먼저 허용해 validation과 rollback 범위를 좁힌다.
  - `included`: pack/profile/policy/source manifest relative paths를 명시한다. source manifest가
    없으면 빈 목록을 쓰고, source coverage가 필요한 package는 package 안에 private source manifest를
    포함해야 한다.
  - `provenance`: package builder, source revision, build timestamp, checksum list를 포함한다.
    secret, provider key, token, customer repository URL은 허용하지 않는다.
- private generated artifact는 public canonical artifact와 같은 path/collection 이름을 쓰지 않는다.
  - install 또는 validation 산출물의 root는 `REVIEW_ENGINE_PRIVATE_ARTIFACT_ROOT`로 명시하게 하고,
    local dev 예시는 `/tmp/review-engine-private-rule-packages/<package_id>/<package_version>/`를 쓴다.
  - JSON dataset 이름은 `<language_id>_<kind>_guideline_records.json`을 유지하되 위 versioned
    package root 아래에만 쓴다.
  - Chroma collection 이름은 sanitized package id/version을 포함한다:
    `guideline_records_<package_id>_<package_version>_<kind>_<language_id>`.
  - retained validation summary는
    `docs/baselines/review_engine/private_rule_packages/YYYY-MM-DD_<package_id>_<package_version>.md`
    형식으로 남긴다.
- install/update/rollback은 existing extension contract 위에 얹는다.
  - install은 package를 staging directory에 unpack한 뒤 package manifest, runtime `manifest.yaml`,
    strict YAML validation, source coverage, duplicate `pack_id`, unknown selected pack reference,
    ingest summary를 모두 통과해야 한다.
  - install이 성공하면 operator가 기존 `REVIEW_ENGINE_EXTENSION_RULE_ROOTS`에 넣을 versioned
    runtime root path를 출력한다. public `review-engine/rules`, committed `review-engine/data`,
    generated Chroma public collection은 수정하지 않는다.
  - update는 새 version을 별도 staging/version directory에서 검증하고, active symlink 또는
    deployment env pointer를 새 versioned runtime root로 바꾸는 방식만 허용한다.
  - rollback은 이전 versioned runtime root로 pointer를 되돌리는 동작으로 정의한다. rollback이
    가능한 동안 이전 generated private artifact root는 삭제하지 않는다.
  - validation gate는 최소한 package-specific strict load/ingest, source coverage matrix,
    runtime private extension test, public-only runtime test를 분리해서 실행한다. 현재 repository
    sample 기준으로는 `ops/scripts/run_review_engine_extension_ci.sh --mode all`이 그 split-gate의
    기준점이다.

착수 후 해야 할 일:

1. `review-engine/examples/extensions/private_org_cpp/` 수준의 filesystem extension을
   installable package shape로 승격할지 결정한다.
2. package validation CLI 또는 existing ingest validation 확장 지점을 정한다.
3. private package가 runtime retrieval, source coverage, lifecycle CLI와 충돌하지 않는지
   deterministic test를 추가한다.
