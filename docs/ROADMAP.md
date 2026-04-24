# Roadmap

## Purpose

이 문서는 앞으로 해야 할 일만 관리한다.
현재 구현 상세는 [CURRENT_SYSTEM.md](/home/et16/work/review_system/docs/CURRENT_SYSTEM.md:1)에 두고,
로드맵에는 완료된 기반 요약과 남은 실행 단위만 남긴다.

마지막 코드 상태 점검일: `2026-04-24`

상태 표기:

- `active`: 바로 작업할 우선순위가 높고, 한 번에 묶을 수 있는 실행 단위가 있다.
- `partial`: 일부 코드 골격이나 테스트는 있으나 운영 완료 기준에는 못 미친다.
- `not_started`: 현재 코드에 구현이 없다.
- `watch`: 새 기능 개발 대상은 아니며 회귀 방지와 운영 관찰만 한다.

## Completed Foundation

아래 항목은 새 로드맵 작업이 아니라 유지/회귀 방지 대상으로 본다.

| Area | 완료된 기반 |
| --- | --- |
| Review-bot Phase A Trust Foundation | runner-level verify path, lifecycle event history, finding outcomes analytics |
| Multi-language core canonicalization | current seed corpus coverage, language/profile/context/dialect routing, provider C++ fixed prior 제거 |
| CUDA native capability expansion | pipeline async, thread block cluster, TMA, WGMMA rule/profile 축 |
| Smoke fixture baseline | lifecycle smoke, mixed-language, curated polyglot, CUDA targeted fixture |
| Wrong-language telemetry loop | provenance/cause/actionability 분리, smoke event와 detector backlog 분리 |
| Provider quality / comparison / density gate | packaged provider quality corpus, deterministic `stub` gate, OpenAI opt-in skip path, provider comparison CLI, fixture `density_contract` |
| Provider-direct smoke split | lifecycle fallback smoke와 direct OpenAI smoke를 별도 신호로 분리 |
| Provider runtime provenance persistence | `ReviewRun.provider_runtime`와 finding payload `provider_runtime` 저장 위치 고정 |

## Work Split

바로 할 일과 나중에 할 일을 아래처럼 나눈다.

### Do Now

- external API quota나 별도 권한 없이 닫을 수 있는 작업만 잡는다.
- 한 commit에서 source/rule/detector/example/validation까지 닫히는 단위를 우선한다.
- deterministic release gate로 먼저 검증 가능한 작업을 우선한다.

### Do Later

아래 항목은 blocker, 선행 조건, 작업 성격에 따라 별도 문서로 분리한다.

- [Deferred Provider And Model Work](/home/et16/work/review_system/docs/deferred/provider_and_model_work.md:1)
- [Deferred Rule Authoring And Editor Work](/home/et16/work/review_system/docs/deferred/rule_authoring_and_editor.md:1)
- [Deferred Platform Expansion](/home/et16/work/review_system/docs/deferred/platform_expansion.md:1)
- [Deferred Automation Work](/home/et16/work/review_system/docs/deferred/automation_work.md:1)

## Now

### 1. Provider Runtime Guardrails

상태: `watch`

최근 완료:

- `GET /internal/review/requests/{review_system}/{project_ref}/{review_request_id}` current-state API가
  마지막 run의 `provider_runtime`(configured/effective provider, fallback 여부/사유)를 직접 반환한다.
- `BOT_PROVIDER`, `BOT_FALLBACK_PROVIDER`를 `openai`/`stub` allowlist로 검증하고,
  unsupported 값은 settings/provider factory에서 startup fail-fast 한다.
- PR summary general note와 publish structured log가
  `provider_runtime_summary`를 함께 노출해 live provider path와 stub fallback path를 바로 읽을 수 있다.
- `ops/scripts/smoke_openai_provider_direct.sh`가 스크립트 위치 기준으로 repo root를 기본 해석하고,
  `REVIEW_SYSTEM_ROOT`, `REVIEW_SYSTEM_ENV_FILE` override와 resolved root/env provenance 출력을 지원한다.
- `review-bot/tests/test_openai_provider_direct_smoke.py`가
  relocated root와 explicit env override contract를 network stub으로 고정한다.

검증 메모:

- 이번 slice는 direct smoke script의 root/env loading contract만 바꿨으므로
  `uv run --project review-bot pytest review-bot/tests/test_openai_provider_direct_smoke.py -q`와
  `bash -n ops/scripts/smoke_openai_provider_direct.sh`만 다시 돌린다.
- deterministic validation은 live direct OpenAI나 lifecycle stub fallback을 쓰지 않고
  script-level network stub만 사용한다.
- local GitLab lifecycle smoke와 live direct OpenAI smoke는 건너뛴다.

남은 구현 작업:

- 없음

### 2. Smoke And Evaluation Hardening

상태: `watch`

운영 원칙:

- `release gate`와 `pre-release smoke`는 이미 분리됐다.
- wrong-language telemetry/backlog snapshot은 정기 checkpoint로만 관찰한다.

남은 구현 작업:

- 없음

### 3. Targeted Rule Expansion

상태: `partial`

최근 완료:

- `DOCKER.1`/`DOCKER.3` shared `latest_tag` detector가
  `FROM image:latest AS runtime # note` shape도 다시 잡도록 넓어졌다.
- `DOCKER.1`/`DOCKER.3` Dockerfile runtime baseline source/rule wording이
  stage alias나 inline note가 있어도 mutable `latest` tag drift가 그대로라는 점을 명시하도록 갱신됐다.
- `DOCKER.1`/`DOCKER.3` bundled code/diff example, diff contract spec, curated polyglot smoke contract가
  aliased/commented `latest` base image shape를 포함하도록 갱신됐다.
- `DOCKER.3`이 stage alias 뒤 trailing inline comment가 붙은
  digestless `FROM image:tag` 경로까지 잡도록 넓어졌다.
- `DOCKER.3` Dockerfile runtime baseline source wording이
  stage alias나 inline note가 있어도 digest pinning 필요성이 그대로라는 점을 명시하도록 갱신됐다.
- `DOCKER.3` bundled code/diff example과 diff contract spec가
  inline-comment digest pinning drift shape를 포함하도록 갱신됐다.
- `DOCKER.SEC.7`이 secret-shaped `ARG`/`ENV` 이름뿐 아니라
  authenticated package/artifact URL을 `ARG`/`ENV`에 직접 싣는 경로까지 잡도록 넓어졌다.
- `DOCKER.SEC.7` source/rule wording이 inline authenticated URL leakage까지 같은 hazard family로 설명하도록 갱신됐다.
- `DOCKER.SEC.7` bundled code/diff example과 diff contract spec가
  authenticated URL shape를 포함하도록 갱신됐다.
- `DOCKER.SEC.1`/`DOCKER.SEC.3` `root_user` detector가
  `USER root`뿐 아니라 numeric root alias인 `USER 0` 경로도 잡도록 넓어졌다.
- `DOCKER.SEC.1`/`DOCKER.SEC.3` Dockerfile runtime identity wording이
  `USER root`와 `USER 0`가 같은 root runtime hazard라는 점을 명시하도록 갱신됐다.
- bundled Docker code/diff example과 curated polyglot smoke contract가
  UID 0 runtime identity shape를 포함하도록 갱신됐다.
- `DOCKER.7`이 bare whole-prefix copy뿐 아니라 ownership-fixing `COPY` option과
  inline note가 붙은 `COPY --from=... /usr/local /usr/local` 경로까지 잡도록 넓어졌다.
- `DOCKER.7` Dockerfile runtime baseline source/rule wording이
  ownership-fixing COPY flags나 inline note가 있어도 runtime surface leak라는 점을 명시하도록 갱신됐다.
- `DOCKER.7` bundled code/diff example과 targeted query conversion regression이
  flagged whole-prefix copy shape를 포함하도록 갱신됐다.
- `GO.13`이 direct chained `json.NewDecoder(...).Decode(...)`뿐 아니라
  `decoder := json.NewDecoder(...)` 뒤 `decoder.Decode(...)` 경로까지 잡도록 넓어졌다.
- `GO.13` bundled code/diff example과 safe regression이 retained decoder shape를 포함하도록 갱신됐다.
- `GO.13`이 Gin `ShouldBindJSON`/`BindJSON` binding 경로까지 잡도록 넓어졌고,
  bundled code/diff example과 safe regression도 같은 handler family에 맞춰 추가됐다.
- `GO.11`이 literal `err == ErrX`뿐 아니라
  `readErr == fs.ErrNotExist` 같은 renamed local error variable sentinel compare까지 잡도록 넓어졌다.
- `GO.11` Go runtime baseline source/rule wording이
  local error variable rename이 있어도 wrapped sentinel branch 안정성이 핵심이라는 점을 명시하도록 갱신됐다.
- `GO.11` bundled code/diff example과 safe regression이
  renamed local error variable compare shape와 `errors.Is(...)` fix path를 함께 포함하도록 갱신됐다.
- `GO.12`가 transaction start 이후 later error branch 안에서만 `Rollback()`을 호출하고
  그대로 `Commit()`까지 가는 경로도 다시 잡도록 넓어졌다.
- `GO.12` Go runtime baseline source/rule wording이
  branch-local rollback later path가 immediate deferred rollback guard를 대체하지 못한다는 점을 명시하도록 갱신됐다.
- `GO.12` bundled code/diff example과 targeted query conversion regression이
  late branch-only rollback shape를 포함하도록 갱신됐다.
- `YAML.K8S.7`이 curated polyglot smoke fixture의 Kubernetes `image: ...:latest`
  경로를 context-specific mutable workload image rule로 잡도록 추가됐다.
- YAML runtime baseline/coverage metadata, bundled Kubernetes code/diff example,
  targeted retrieval regression, curated polyglot smoke contract가 같은 latest-tag path를 포함하도록 갱신됐다.

남아 있는 우선 gap:

- 명시된 1순위 gap은 없음
- 다음 후보를 고르려면 repo-local telemetry/smoke checkpoint artifact를 먼저 확보해야 한다

다음 작업:

1. fresh telemetry 또는 smoke checkpoint를 repo 안에 남기고 다음 under-trigger 근거를 고정한다.
2. 그 evidence에서 under-trigger gap 하나만 골라 source atom 또는 source 문서, detector/rule/example을 같은 단위에서 갱신한다.
3. `review-engine`만 바뀌면 rule/retrieval baseline만 다시 돌리고, `review-bot`이나 lifecycle 영향이 생기면 그에 맞는 regression과 smoke 범위를 추가한다.
4. 같은 family에 under-trigger가 더 남아 있어도 이번 slice 밖이면 다음 roadmap unit로 분리한다.

검증 메모:

- 이번 slice는 `review-engine` Docker runtime identity source/rule wording, bundled code/diff example,
  curated polyglot smoke contract를 변경했고 ingest 결과 Dockerfile active guideline dataset도 함께 갱신했다.
- rerun:
  - `uv run --project review-engine python -m review_engine.cli.ingest_guidelines`
  - `uv run --project review-engine pytest review-engine/tests/test_query_conversion.py review-engine/tests/test_expected_examples.py review-engine/tests/test_smoke_fixture_contracts.py review-engine/tests/test_multilang_regressions.py review-engine/tests/test_source_coverage_matrix.py -q`
  - `uv run --project review-engine python -m review_engine.cli.evaluate_examples`
  - `uv run --project review-engine python -m review_engine.cli.evaluate_diff_contracts`
- broader `review-engine` pytest, `review-bot`/`review-platform` tests,
  GitLab lifecycle smoke, mixed-language smoke, direct OpenAI/provider validation은 이번 범위 밖이라 생략했다.

현재 1순위 후보:

- fresh telemetry/smoke checkpoint를 남긴 뒤 다시 고를 다음 under-trigger gap

완료 기준:

- source, coverage, rule/policy, detector, regression, ingest 검증이 한 번에 들어간다.
- rule 추가가 provider/ranking/density baseline을 악화시키지 않는다.

### 4. Review-Bot Context And UX

상태: `partial`

최근 완료:

- `@review-bot summarize`가 lightweight general note contract로 추가되어
  최신 run/head, provider provenance, aggregate backlog/suppress count만 빠르게 보여 주도록 고정했다.
- `summarize`는 same-purpose general note upsert를 사용하고,
  GitLab note parser/help note도 새 명령을 함께 안내하도록 갱신됐다.
- `@review-bot walkthrough`가 note-first UX 가이드로 추가되어
  `summarize -> backlog -> full-report` 읽는 순서와 backlog reason 해석 순서를 general note 하나로 고정했다.
- `walkthrough`도 same-purpose general note upsert를 사용하고,
  GitLab note parser/help note와 canonical 문서가 새 명령을 함께 안내하도록 갱신됐다.
- `full-report`/`backlog` general note가 각 항목의 `disposition`/`reason`을 짧은 한국어 surfacing reason으로 함께 보여 주도록 바뀌었다.
- raw `reason` 코드는 그대로 유지해 운영자가 machine-readable state를 잃지 않으면서도, note만 읽는 사용자는 왜 backlog/suppress/pending 상태인지 바로 볼 수 있다.
- review unit split 로직을 `review_bot.review_units` helper로 분리해
  runtime과 audit가 같은 fixed-line hunk 분할 규칙을 공유하도록 고정했다.
- deterministic `review_unit_split_audit` corpus/CLI와
  repo-local artifact `docs/baselines/review_bot/review_unit_split_audit_2026-04-24.md`를 추가해
  long hunk split 우선 언어와 monitor-only 언어를 repo-local deterministic audit로 고정했다.
- `yaml` long added hunk가 raw 80-line cut 대신 safe list-item / mapping boundary를 우선 쓰는
  syntax-aware split prototype을 갖게 됐고, runner detect/sync path도 같은 file/language-aware split 규칙을 공유한다.
- `review_unit_split_audit` artifact가 갱신되어
  `python`, `yaml`, `typescript`는 `current_hunk_split_ok`로 내려가고 `go`만 monitor-only로 남았다.
- `review-bot/tests/test_review_runner.py::test_review_runner_yaml_syntax_aware_split_uses_safe_boundary_for_anchor_and_fingerprint`가
  long YAML block의 후속 finding anchor/fingerprint 시작선이 raw line `81`이 아니라 safe boundary line `80`에 고정되도록 회귀를 추가했다.
- `.tsx` long added hunk가 sibling JSX boundary를 우선 쓰는
  syntax-aware split prototype을 갖게 됐고, runtime과 deterministic audit가 같은 safe boundary line `78`을 공유한다.
- `review-bot/tests/test_review_runner.py::test_review_runner_typescript_syntax_aware_split_uses_safe_boundary_for_anchor_and_fingerprint`가
  long TSX component의 후속 finding anchor/fingerprint 시작선이 raw line `81`이 아니라 safe boundary line `78`에 고정되도록 회귀를 추가했다.
- `python` long added hunk가 sibling statement boundary를 우선 쓰는
  syntax-aware split prototype을 갖게 됐고, detect path와 sync/reclassification path 모두 `.py` path normalization으로 같은 safe boundary line `80`을 공유한다.
- `review-bot/tests/test_review_runner.py::test_review_runner_python_syntax_aware_split_uses_safe_boundary_for_anchor_and_fingerprint`가
  long Python handler의 후속 finding anchor/fingerprint 시작선이 raw line `81`이 아니라 safe boundary line `80`에 고정되도록 회귀를 추가했다.
- same-file `file_context` retrieval과 project-scoped `similar_code` index/search를 별도 경로로 고정했다.
- `review-engine` `/codebase/index`, `/codebase/search`, `CodebaseStore`가 optional `project_ref` scope를 지원하고,
  `project_ref`를 생략하면 legacy shared scope로 남도록 했다.
- `review-bot` detect path가 similar-code 검색마다 현재 `review_request.project_ref`를 전달하고,
  legacy search client signature를 쓰는 test stub도 fallback으로 계속 허용한다.
- `review-bot` learned `rule_no` weight가 전체 프로젝트 공통 baseline과
  현재 `project_ref` local override를 분리해 계산되도록 바뀌었다.
- project-local override는 같은 rule의 distinct surfaced fingerprint가 충분할 때만 덮어쓰므로
  특정 프로젝트의 feedback이 다른 프로젝트 detect score를 흔들지 않는다.
- `review-bot/tests/test_review_runner.py`가
  project-local override 적용과 small-sample global fallback 회귀를 함께 고정한다.
- `.review-bot.yaml`, `summarize`, `ask`, walkthrough note를 다시 비교해
  현재 note-first UX 확장 순서를 `summarize -> walkthrough note -> .review-bot.yaml -> ask`로 고정했다.
- `summarize`는 existing general note stack을 재사용하는 가장 작은 UX slice로 두고,
  walkthrough note는 그 다음 note-family 확장, `.review-bot.yaml`과 `ask`는 더 넓은 product surface라 뒤로 미룬다.

다음 작업:

1. `.review-bot.yaml`은 policy/env precedence와 운영 표현 경계가 정리된 뒤 잡는다.
2. `ask`는 retrieval/session boundary와 provider cost/latency까지 함께 정리해야 하므로 마지막으로 둔다.

검증 메모:

- 이번 slice는 `review-bot` note parser/help text와 general note renderer에 `walkthrough` command를 추가했다.
- rerun:
  - `env UV_CACHE_DIR=/tmp/uv-cache uv run --project review-bot pytest review-bot/tests/test_review_runner.py::test_render_walkthrough_note_guides_note_order_and_backlog_reasons review-bot/tests/test_review_runner.py::test_post_walkthrough_note_upserts_same_purpose_general_note review-bot/tests/test_review_runner.py::test_render_help_note_lists_walkthrough_command review-bot/tests/test_api_queue.py::test_gitlab_note_hook_posts_walkthrough_note_without_enqueue review-bot/tests/test_api_queue.py::test_extract_gitlab_note_command_recognizes_supported_commands -q`
- broader `review-bot` pytest, `review-engine`/`review-platform` tests, GitLab lifecycle smoke, mixed-language smoke, direct OpenAI/provider validation은 note-only UX 범위라 생략했다.
- direct OpenAI, stub fallback, lifecycle smoke는 모두 이번 slice validation에 사용하지 않았다.

완료 기준:

- backlog와 surfacing reason이 사용자에게 더 잘 설명된다.
- syntax-aware split 우선 언어가 repo-local deterministic audit로 고정된다.
- project-local feedback이 global quality metric을 왜곡하지 않는다.
- context retrieval이 false-positive를 줄이는지 deterministic fixture로 확인된다.

### 5. Organization Rule Extension

상태: `watch`

최근 완료:

- `review-engine/examples/extensions/private_org_cpp/`에
  manifest/pack/profile/policy를 갖춘 opt-in private extension sample root를 추가했다.
- `ops/scripts/run_review_engine_extension_ci.sh`가
  repo-local deterministic release gate를 `public-only`와 `private-enabled` 경로로 분리해
  CI caller가 public core와 repo sample private extension 검증을 독립적으로 호출할 수 있게 했다.
- `review-engine/tests/test_rule_runtime.py`와
  `review-engine/tests/test_rule_runtime_private_extension.py`가 분리되어
  public loader/runtime 회귀와 repo sample private extension 회귀가 서로 다른 gate에서 돌 수 있게 됐다.
- `review-engine/tests/test_rule_runtime_private_extension.py`가
  repo sample root load와 ingest summary 둘 다에서 organization policy record와
  public rule override/exclude 경로를 회귀로 고정한다.
- `docs/CURRENT_SYSTEM.md`와 sample extension README가
  dev/prod extension failure policy를 canonical하게 문서화하고,
  `REVIEW_ENGINE_EXTENSION_RULE_ROOTS`/`REVIEW_ENGINE_STRICT_EXTENSION_LOADING`
  설정 예제를 함께 고정한다.
- `review-engine/tests/test_rule_runtime.py`가
  `REVIEW_ENGINE_STRICT_EXTENSION_LOADING=0`이어도
  명시한 filesystem extension root manifest/YAML은 fail-fast 한다는 경계를 회귀로 고정한다.
- `pack_id`를 canonical pack identity로 유지하고,
  `source_family`는 API/analytics/chroma compatibility를 위한 legacy read-only alias로 고정했다.
- runtime model이 `pack_id`/`source_family` mismatch를 fail-fast 하고,
  legacy-only payload는 canonical `pack_id`로 동기화하는 회귀를 추가했다.
- `docs/API_CONTRACTS.md`와 `review-engine` search-service metadata regression이
  응답에서 `pack_id`와 `source_family`가 같은 identity를 노출하는 장기 호환 계약을 고정한다.
- sample private extension root와 `docs/CURRENT_SYSTEM.md`가
  `pack_weight`는 policy `pack_weights`, `reference_only`는 rule entry `reviewability`,
  `conflict_action`은 policy override/exclusion이 해석된 runtime state라는 canonical 경계를 고정한다.
- sample extension pack이 `ORG.REF.1` reference-only rule을 추가해
  private extension에서도 reference guidance가 `reviewability` 경로로만 표현됨을 repo-local fixture로 고정한다.
- `review-engine` authoring model이
  rule entry `default_action`과 policy `defaults.conflict_action`의 non-`compatible` 값을 reject해
  override/exclusion은 policy surface, reference guidance는 `reviewability` surface로 분리한다.

남은 구현 작업:

- 없음

검증 메모:

- 이번 slice는 `review-engine` authoring model, repo sample private extension root,
  canonical 문서에서 `pack_weight`/`reference_only`/`conflict_action` 운영 표현 경계를 고정했다.
- rerun:
  - `uv run --project review-engine pytest review-engine/tests/test_rule_runtime.py review-engine/tests/test_rule_runtime_private_extension.py review-engine/tests/test_review_metadata.py -q`
- broader `review-engine` pytest, ingest/retrieval baseline, `review-bot`/`review-platform` tests,
  GitLab smoke, provider/direct OpenAI validation은 extension authoring/runtime contract 범위라 생략했다.

완료 기준:

- public core는 private extension 없이 항상 동작한다.
- private extension은 명시 설정으로만 로드된다.
- private rule priority가 retrieval/rerank/prompt/detector에서 일관된다.
- public/private 경계가 깨지면 CI에서 잡힌다.

## Suggested Next Step

현재 가장 자연스러운 다음 작업은 local `review-bot` API/analytics endpoint가 준비된 환경에서
`Targeted Rule Expansion`용 fresh telemetry/smoke checkpoint artifact를 먼저 남긴 뒤,
그 evidence에서 다음 under-trigger gap 하나를 다시 골라 같은 source/rule/example 단위로 닫는 것이다.

이유:

- `Provider Runtime Guardrails`는 watch 상태로 내려갔고 남은 실행 단위가 없다.
- `Targeted Rule Expansion`은 여전히 source/rule/detector/example/validation을 한 번에 닫을 수 있는
  가장 작은 product-facing 실행 단위를 유지하고 있다.
- 다만 현재 repo-local checkpoint artifact가 없고 local API/analytics가 살아 있는 환경이 선행 조건이므로,
  근거 없이 임의 rule slice를 고르지 않도록 evidence refresh를 다음 선행 조건으로 둔다.

## Queued After Main Roadmap

main `ROADMAP.md`의 현재 항목을 다 돌린 뒤 곧바로 이어서 할 후보는 아래 순서로 관리한다.

### 6. Roadmap Automation Audit Artifact

상태: `watch`

최근 완료:

- `docs/baselines/roadmap_automation/README.md`가
  retained blocker artifact의 canonical directory, filename, required entry fields
  (`date`, `attempt`, `blocked_unit`, `reason`)와 Markdown entry shape를 고정했다.
- `ops/scripts/advance_roadmap_with_codex.sh`가
  blocked iteration의 normalized summary를 run 동안 임시로 모았다가
  종료 시점 또는 completed iteration commit 직전에
  `docs/baselines/roadmap_automation/blocked_roadmap_units_YYYY-MM-DD.md`로 append하도록 바뀌었다.
- 같은 script prompt가 blocked 응답에 `BLOCKED_UNIT`, `BLOCKER_TYPE`, `BLOCKED_REASON`
  structured line을 요구하고, artifact append는 field가 없는 legacy blocked output에도
  fallback summary를 남기도록 고정됐다.
- `docs/baselines/roadmap_automation/README.md`가
  retained blocker artifact만을 canonical source로 쓰는 repeated blocker review procedure를 추가했고,
  `blocked_unit`/`blocker_type` 집계 명령과 append-only 운영 규칙을 함께 고정했다.

남은 구현 작업:

- 없음

검증 메모:

- 이번 slice는 roadmap automation retained artifact README에 repeated blocker review procedure를 추가했다.
- rerun:
  - `bash -n ops/scripts/advance_roadmap_with_codex.sh`
- broader `review-engine`/`review-bot`/`review-platform` tests, GitLab smoke,
  provider/direct OpenAI validation은 roadmap automation script 범위 밖이라 생략했다.

완료 기준:

- blocked skip 결과가 임시 파일이 아니라 repo-local artifact로 남는다.
- 반복 blocker를 roadmap prioritization 입력으로 재사용할 수 있다.

### 7. Minimal Rule Lifecycle CLI

상태: `partial`

최근 완료:

- `review_engine.cli.rule_lifecycle`가 canonical YAML runtime을 직접 읽는
  read-only `list`/`show` command를 추가해 generated dataset이나 ingest 없이도
  현재 selected runtime의 rule state를 바로 조회할 수 있게 됐다.
- CLI 출력은 `source_of_truth=canonical_yaml`, selected `language/profile/context/dialect`,
  `selected_pack_ids`, `public_rule_root`/`extension_rule_roots`를 함께 내보내서
  runtime selection과 source-of-truth 경계를 한 번에 읽게 고정했다.
- `review-engine/tests/test_rule_lifecycle_cli.py`가
  `list`/`show`가 temp data dir을 건드리지 않고 canonical YAML만 읽는 회귀를 고정했다.
- `disable`/`enable` command가 selected runtime pack manifest를 직접 읽어
  canonical pack YAML entry 하나의 `enabled` field만 수정하도록 추가됐다.
- mutation output은 `write_boundary=canonical_pack_yaml`, `source_path`,
  `previous_enabled`, `updated_enabled`를 함께 내보내서
  generated artifact가 아니라 canonical YAML만 바꿨다는 경계를 바로 보여 준다.
- `review-engine/tests/test_rule_lifecycle_cli.py`가
  temp rule root 기준 disable/enable/no-`pack-id` ambiguity 회귀를 추가해
  disabled entry 재활성화와 pack disambiguation contract를 deterministic하게 고정했다.
- `disable`/`enable` mutation output이 structured `validation_plan`을 함께 내보내
  changed rule을 같은 selected runtime에서 다시 `show`하고, 이어서 `ingest_guidelines`와
  targeted pytest를 어떤 순서로 다시 돌릴지 command 단위로 바로 읽게 됐다.
- `review-engine/tests/test_rule_lifecycle_cli.py`가
  mutation payload의 `validation_plan` scope, runtime selector, follow-up command bundle 회귀를
  추가해 post-mutation deterministic validation 연결을 고정했다.
- `list --state disabled`와 `show --rule ...`가 selected pack의 canonical YAML을 함께 읽어
  runtime에서 빠진 `enabled: false` entry도 `runtime_state=disabled`로 다시 조회할 수 있게 됐다.
- `review-engine/tests/test_rule_lifecycle_cli.py`가
  disabled entry list/show가 temp rule root 기준으로 canonical YAML만 읽고
  temp data dir을 건드리지 않는 회귀를 추가해 re-enable 전 inspection 경로를 고정했다.
- `enable-pack`/`disable-pack` command가 selected runtime의 single canonical profile YAML만 수정해
  profile-level pack membership on/off를 entry-level rule toggle과 분리된 write boundary로 추가했다.
- profile YAML이 explicit `enabled_packs`/`shared_packs` 없이 `default_enabled` fallback에 의존하면,
  pack mutation이 현재 runtime selection을 explicit profile pack list로 materialize한 뒤 target pack on/off를 적용하도록 고정했다.
- selected runtime이 여러 profile YAML merge 결과면
  pack mutation이 single write boundary를 잃지 않도록 fail-fast 하게 막았다.
- `review-engine/tests/test_rule_lifecycle_cli.py`가
  explicit profile pack toggle, fallback materialization, new pack enable, merged-profile write-boundary refusal 회귀를 추가했다.

범위:

- `list`
- `show`
- `disable`
- `enable`
- `disable-pack`
- `enable-pack`

다음 작업:

1. pack-level mutation을 넣게 되면 entry-level toggle과 운영 경계를 분리해 문서화한다.

검증 메모:

- 이번 slice는 lifecycle CLI에 profile-level pack on/off를 추가해
  canonical profile YAML write boundary, `default_enabled` fallback materialization, merged-profile refusal contract를 고정했다.
- rerun:
  - `env UV_CACHE_DIR=/tmp/uv-cache uv run --project review-engine ruff check review-engine/review_engine/cli/rule_lifecycle.py review-engine/tests/test_rule_lifecycle_cli.py`
  - `env UV_CACHE_DIR=/tmp/uv-cache uv run --project review-engine pytest review-engine/tests/test_rule_lifecycle_cli.py review-engine/tests/test_rule_runtime.py -q`
- profile pack mutation path는 temp rule root를 쓰는 CLI test로 검증했고,
  repo canonical YAML 자체는 validation 중 수정하지 않았다.
- `ingest_guidelines`와 broader retrieval baseline은 이번 slice가 canonical YAML inspection CLI 범위라 직접 rerun하지 않았다.
- broader `review-engine` pytest, `review-bot`/`review-platform` tests,
  GitLab smoke, provider/direct OpenAI validation은 lifecycle CLI inspection 범위라 생략했다.

완료 기준:

- 최소 CLI만으로 rule 조회, entry on/off, profile pack on/off 관리가 가능하다.
- generated artifact와 canonical source 경계가 흐려지지 않는다.

### 8. OpenAI-Compatible Local LLM Backend

상태: `not_started`

다음 작업:

1. OpenAI-compatible endpoint 전략을 고른다.
2. fallback 정책과 structured output 품질 기준을 정한다.
3. local backend smoke와 provider quality baseline 범위를 정한다.

완료 기준:

- OpenAI API와 분리된 local backend 실험 경로가 생긴다.
- live provider / local provider / stub fallback을 비교 가능한 구조로 확장할 수 있다.

## Not Now

지금 당장 잡지 않는 대표 항목은 아래와 같다.

- provider / ranking / density direct tuning
  - 이유: direct OpenAI path가 현재 `insufficient_quota`로 막혀 있다.
- manual rule editor / authoring UX
  - 이유: 현재는 YAML/Git 기반 수동 편집 토대는 있지만 editor/UI와 lifecycle CLI를 바로 넣을 시점은 아니다.
- multi-SCM adapter expansion
  - 이유: GitHub/Gerrit adapter는 설계/fixture/smoke까지 한 단위가 커서 현재 우선순위보다 뒤다.
- review-bot apply / auto-fix automation
  - 이유: trust metric, low-risk fix class, audit/rollback 경계가 선행 조건이다.

## Validation Baseline

`release gate`:

- network 없이 재현 가능한 deterministic 검증이다.
- 일반 PR 확인이나 기본 CI 후보는 이 범주를 기본으로 사용한다.

일반 변경:

```bash
uv run --project review-engine pytest review-engine/tests -q
uv run --project review-bot pytest review-bot/tests -q
uv run --project review-platform pytest review-platform/tests/test_pr_flow.py -q
```

Rule/retrieval 변경:

```bash
uv run --project review-engine python -m review_engine.cli.ingest_guidelines
uv run --project review-engine python -m review_engine.cli.evaluate_examples
uv run --project review-engine python -m review_engine.cli.evaluate_diff_contracts
```

Provider/ranking/density 변경:

```bash
uv run --project review-bot pytest review-bot/tests/test_multilang_smoke_fixture.py review-bot/tests/test_provider_quality.py -q
uv run --project review-bot python -m review_bot.cli.evaluate_provider_quality \
  --provider stub \
  --json-output /tmp/provider_quality_stub.json
```

`pre-release smoke`:

- local GitLab 상태, webhook, replay fixture가 준비된 환경에서만 돌린다.
- adapter/lifecycle/routing 변경이나 배포 전 확인에 사용한다.

GitLab/lifecycle 변경:

```bash
bash ops/scripts/smoke_local_gitlab_lifecycle_review.sh
```

Multilanguage/routing 변경:

```bash
bash ops/scripts/smoke_local_gitlab_multilang_review.sh --fixture synthetic-mixed-language
bash ops/scripts/smoke_local_gitlab_multilang_review.sh --fixture curated-polyglot --project-ref root/review-system-curated-polyglot-smoke
bash ops/scripts/smoke_local_gitlab_multilang_review.sh --fixture cuda-targeted --project-ref root/review-system-cuda-smoke
```

direct provider / comparison artifact:

- deterministic release gate와 별개로 본다.
- `evaluate_provider_quality --provider openai`는 `OPENAI_API_KEY`가 없으면 `skipped` artifact를 남기고 성공 종료할 수 있다.
- fallback이 켜져 있으면 lifecycle smoke만으로 live OpenAI direct 성공을 증명할 수 없다.

```bash
uv run --project review-bot python -m review_bot.cli.evaluate_provider_quality \
  --provider openai \
  --json-output /tmp/provider_quality_openai.json
uv run --project review-bot python -m review_bot.cli.compare_provider_quality \
  --stub-json /tmp/provider_quality_stub.json \
  --openai-json /tmp/provider_quality_openai.json
```
