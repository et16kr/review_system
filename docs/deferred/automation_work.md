# Deferred Automation Work

## Purpose

이 문서는 auto-fix, approval, audit, rollback처럼 신뢰 경계가 중요한 자동화 작업을 모아 둔다.

마지막 코드 상태 점검일: `2026-04-24`

## 1. Review-Bot Apply / Auto-Fix Automation

현재 미루는 이유:

- roadmap 자체가 trust metric과 low-risk fix class를 선행 조건으로 요구한다.
- 지금 바로 자동 수정에 들어가면 false-positive, audit, rollback 경계가 불명확하다.

착수 전 선행 조건:

1. `fix_conversion_rate_28d`가 2 phase 이상 plateau인지 확인한다.
2. verify/ranking/provider tuning만으로 false-positive 저감이 정체인지 확인한다.
3. low-risk fix class를 충분히 좁게 정의한다.
4. reviewer approval, audit, rollback 정책을 먼저 문서화한다.
5. roadmap automation이 blocked unit을 retained artifact로 남기고, direct provider preflight가
   bounded runtime 안에서 끝나는지 먼저 확인한다.

착수 후 해야 할 일:

1. `@review-bot apply` 전에 low-risk fix class와 권한 모델을 정의한다.
2. patch 생성, audit, rollback, reviewer approval 경계를 설계한다.
3. provider `auto_fix_lines` payload를 실제 patch application flow와 연결할지 결정한다.
4. multi-reviewer parallel agent나 IDE 실시간 리뷰는 trust metric이 안정된 뒤 재평가한다.

## Post-Review Boundary

`2026-04-24` 리뷰 라운드 기준으로 auto-fix automation은 계속 deferred다. 신뢰 metric, low-risk
fix class, approval/audit/rollback 정책이 먼저 필요하다.

반대로 아래 automation guardrail은 auto-fix와 관계없이 즉시 수정할 항목이다.

- review-roadmap blocked unit을 `/tmp` scratch가 아니라 retained artifact로 남기는 것
- OpenAI direct smoke preflight에 timeout을 두어 automation loop가 멈추지 않게 하는 것

이 두 항목은 deferred automation의 선행 조건으로 기록하지만, auto-fix 설계가 시작될 때까지
미루지 않는다.

## Auto-Fix Safety Readiness Packet

이 패킷은 future `@review-bot apply`를 바로 구현하자는 결정이 아니다. 목적은 실제 patch
application flow를 시작하기 전에 low-risk fix class, reviewer approval, audit, rollback,
provider `auto_fix_lines` 연결 기준을 좁혀 두는 것이다.

### Low-Risk Fix Class

future `@review-bot apply` v1 후보는 아래 조건을 모두 만족하는 finding으로 제한한다.

1. 동일 `ReviewRequestKey(review_system, project_ref, review_request_id)`의 최신 review run과
   현재 remote head SHA가 일치한다.
2. finding이 현재 diff의 단일 파일, 단일 contiguous hunk, 단일 reviewer-visible thread에 매핑된다.
3. patch가 새 파일 생성, 파일 삭제, rename, mode change, binary/generated/vendor/lockfile 변경을
   포함하지 않는다.
4. fix가 public API, auth/permission, crypto, schema migration, concurrency, resource lifetime,
   data deletion, dependency version, build pipeline 같은 cross-cutting behavior를 바꾸지 않는다.
5. rule family가 deterministic local validation으로 확인 가능한 narrow edit를 요구한다.
6. verifier가 fix 이후 같은 finding이 사라지고 새 high-severity finding이 생기지 않았다는 신호를
   같은 head에서 낸다.
7. provider/runtime provenance, rule id, evidence snippet, patch digest가 audit record에 남아 있다.

처음 허용할 수 있는 fix family 후보는 더 좁게 본다.

- formatting-only whitespace 또는 trailing newline 정리
- comment/doc typo처럼 executable behavior를 바꾸지 않는 single-line correction
- 명백한 unused import 제거처럼 language tooling이 deterministic하게 확인하는 single-file cleanup
- existing suggestion block이 현재 diff hunk 안의 replacement로 정확히 닫히는 one-hunk edit

아래 경우는 v1에서 제외한다.

- multi-file, multi-hunk, generated artifact, lockfile, vendored dependency, binary asset 변경
- test snapshot 대량 갱신, migration, dependency upgrade, config/security policy 변경
- provider가 reasoning만 제공하고 concrete replacement를 제공하지 않은 finding
- stale head, unresolved merge conflict, adapter file-content fetch 실패, verifier unavailable/timeout
- reviewer가 이미 같은 thread에 human reply를 달아 disposition이 바뀐 finding

### Approval, Audit, Rollback

`review`, `summarize`, `walkthrough`, `full-report`, `backlog`, `help`는 자동 수정 권한을 갖지
않는다. future `@review-bot apply`도 explicit reviewer action이며, detect/publish lifecycle의
부수 효과로 실행되면 안 된다.

v1 approval boundary:

1. apply 요청자는 adapter가 확인할 수 있는 MR/PR write 권한자여야 한다.
2. apply는 finding/thread id 또는 bot이 발행한 stable apply token을 지정해야 한다.
3. bot은 mutation 전에 intended patch preview와 validation status를 same-purpose note로 남긴다.
4. target branch에 직접 push하지 않고, adapter가 지원하는 suggestion/apply branch/commit proposal
   중 가장 좁은 mutation surface를 사용한다.
5. remote head SHA가 preview 이후 바뀌면 apply를 중단하고 새 review run을 요구한다.

audit record는 최소한 아래 값을 durable event로 남긴다.

- canonical `ReviewRequestKey`
- run id, finding id, rule id, severity, confidence, actionability
- adapter thread/comment refs와 request-scoped remote id
- actor ref, command text, command timestamp, adapter authorization result
- before/after head SHA, patch digest, changed paths, changed line range
- provider runtime provenance와 verifier result
- final apply status: `previewed`, `approved`, `applied`, `rejected`, `stale_head`, `validation_failed`,
  `rolled_back`

rollback boundary:

1. bot-created mutation은 revert 가능한 commit/proposal id를 audit record에 저장한다.
2. rollback은 bot이 만든 patch에만 허용하고, human-authored follow-up commit은 자동 revert하지 않는다.
3. rollback 요청도 explicit reviewer command와 current head check를 요구한다.
4. rollback 실패는 silent retry가 아니라 visible note와 retained diagnostic artifact로 남긴다.

### Provider `auto_fix_lines` Boundary

현재 provider `auto_fix_lines`는 GitLab suggestion block으로 렌더링되는 review hint다. 이것만으로
patch application source of truth가 되지 않는다.

future apply flow에 연결하려면 아래 조건을 먼저 만족해야 한다.

1. `auto_fix_lines`가 current diff hunk의 exact replacement range와 losslessly 연결된다.
2. replacement가 placeholder, ellipsis, unrelated context, markdown fence marker를 포함하지 않는다.
3. provider suggestion과 deterministic patch builder가 같은 digest를 만든다.
4. language-aware syntax check 또는 project-level deterministic validation이 bounded runtime 안에서
   실행된다.
5. verifier가 applied patch의 same-finding resolution을 확인한다.

이 조건을 만족하지 못하면 `auto_fix_lines`는 계속 suggestion-only artifact로 둔다. multi-file
patch generation, semantic refactor, test update generation은 별도 patch model과 human review
workflow가 생기기 전까지 deferred다.
