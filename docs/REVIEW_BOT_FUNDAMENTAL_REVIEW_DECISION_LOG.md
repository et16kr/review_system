# Review Bot Fundamental Review — Decision Log

- 문서 상태: Current (companion to `REVIEW_BOT_FUNDAMENTAL_REVIEW.md` and `REVIEW_BOT_FUNDAMENTAL_REVIEW_DETAILED_DESIGN.md`)
- 작성일: 2026-04-21
- 작성자: Claude
- 생성 계기: `REVIEW_BOT_FUNDAMENTAL_REVIEW_DOCUMENT_FLOW_ASSESSMENT.md` §8의
  "decision log를 두자"는 제안을 실제 파일로 구현한다.

## 0. 이 문서는 무엇인가

11개에 이르는 `REVIEW_BOT_FUNDAMENTAL_REVIEW*` 문서 시리즈에서
**이미 합의되어 다시 논의할 필요가 없는 결정**만 모은 단일 파일.

핵심 규칙:

- 여기 박힌 결정은 **closed**다. 다음 라운드에서 되돌리려면 이 log에 직접 변경 항목을 추가해야 한다.
- 새 버전 통합본(V6, V7 ...)을 쓰기 전에 **이 log부터 먼저 본다.**
- 새 PromQL / 새 state value / 새 endpoint를 문서에 쓰기 전
  §7 "existence-assumption drift guard" 체크리스트를 통과해야 한다.
- 각 결정은 근거 문서를 남긴다. 갱신/철회 시 근거도 갱신.

증거 층위는 기존 관습대로 `[code-verified]` / `[design-inference]` / `[market-informed]`.

## 1. 시스템 방향 (closed)

### D1.1 현재 구조는 유지 가치가 있다
- 결정: inline-first, detect/publish/sync 분리, fingerprint+anchor_signature dedupe,
  `ThreadSyncState` 중심 backlog, feedback-aware suppression, explicit command parser 유지.
- 근거: V2 §6.1, V4 §6.1, V5 §3.1. 모든 라운드에서 뒤집힌 적 없음.

### D1.2 다음 투자 우선순위
- 결정: **신뢰도 → context → learning/UX → automation** 순서를 유지한다.
- 근거: 원본 §0, V4 §1, V5 §0. 모든 평가가 이 순서에 동의.

### D1.3 탐지 복잡도 증가는 우선순위 아님
- 결정: 다음 단계는 "더 많이 지적하는 봇"이 아니라 "더 믿을 수 있고 맥락을 알고 실행 가능한 제안을 하는 봇".
- 근거: 원본 §0, V5 §0.

## 2. 트리거 모델 (closed)

### D2.1 현 구조는 Note Hook mention driven
- 결정: `Merge Request Hook`은 `manual_review_requires_bot_mention_comment`로 무시.
  review run 생성 경로는 (a) `POST /internal/review/runs`, (b) `Note Hook` mention.
- 근거: `[code-verified]` `review_bot/api/main.py:191-197`.

### D2.2 자동 inline review는 baseline 확보 전 금지
- 결정: P0.1 옵션 (c) "자동 review까지 확장"은 baseline-v1 확보 전까지 금지.
- 근거: V4 §7 P0.1, V5 §8 P0.1.

### D2.3 walkthrough 자동 게시는 (b) 부분 확장 모델에서만 허용
- 결정: MR hook을 "metadata refresh / sync / optional walkthrough trigger"로만 도입하는 (b) 선택지 하에서 walkthrough auto-post를 검토. (a) 유지 상태에서는 on-demand `@review-bot summarize`만.
- 근거: V4 §7 P0.1 + Phase C4, V5 §8 P0.1 + Phase C.

## 3. 데이터 모델 / Field Naming (closed)

### D3.1 `resolution_reason` naming
- 결정: 모델 필드명은 **`resolution_reason`** (not `resolved_reason`). 이 naming을 모든 문서에서 통일.
- 근거: `[code-verified]` `review_bot/db/models.py` + `review_runner.py:608/851/858/1565/1574`.

### D3.2 `resolution_reason` 현재값 (5개)
- 결정: 현 코드에 실제 대입되는 값은 5개뿐이다.
  1. `anchor_changed` (`review_runner.py:608`)
  2. `no_longer_eligible` (`review_runner.py:851`)
  3. `resolve_failed` (`review_runner.py:858`)
  4. `remote_resolved` (`review_runner.py:1565`)
  5. `remote_reopened` (`review_runner.py:1574`)
- 근거: `[code-verified]`.

### D3.3 `resolution_reason` 추가 후보 (Phase A에서 도입)
- 결정: Phase A1에서 아래 두 값을 추가 검토.
  - `fixed_in_followup_commit`
  - `remote_resolved_manual_only`
- 근거: V4 §7 P0.2, V5 §8 P0.2.

### D3.4 severity taxonomy migration
- 결정: 새 taxonomy = `nitpick | suggestion | warning | critical`.
  기존 `low | medium | high`는 **alias**로 유지 (rename 아님).
- 근거: V4 §9 A2, V5 §9 Phase A.

## 4. KPI Naming (closed)

### D4.1 `acceptance_rate`는 단독 이름 금지
- 결정: 모호한 `acceptance_rate` 단독 사용 금지. 아래 두 개로 분리.
  - `fix_confirmation_rate` — resolved 중 fix 확인 비율 (분모: resolved distinct)
  - `fix_conversion_rate` — surfaced cohort 중 SLA 내 fixed 전환 비율
- 근거: V3 P0.3, V4 P0.3, V5 §6.1, V4_EVALUATION §3.2.

### D4.2 외부 커뮤니케이션 default mapping
- 결정: 어쩔 수 없이 `acceptance_rate`를 쓸 때는 기본 의미를 `fix_conversion_rate`로 간주.
  단 내부 대시보드는 별도 이름으로 표기.
- 근거: V4 P0.3.

### D4.3 canonical window 기본값
- 결정: canonical window는 아래를 기본으로 사용.
  - `fix_confirmation_rate_14d`
  - `fix_conversion_rate_28d`
  - `human_resolve_rate_14d`
  - `publish_volume_7d` / `suppress_volume_7d` / `feedback_ignore_rate_7d` / `verify_drop_rate_7d`
- 근거: V5 §6.1.

## 5. 측정 모델 (closed) — **가장 중요한 결정**

### D5.1 측정은 2-plane으로 분리한다
- 결정:
  - **Plane A — Operational Metrics (Prometheus)**: publish/suppress/resolve *event* volume, verify attempt/drop, feedback command event, queue depth/duration.
  - **Plane B — Quality Analytics (DB / API / rollup)**: distinct fingerprint 기반 fix confirmation, fix conversion, human resolve, false positive feedback.
- 근거: V5 §5, V4_EVALUATION §3.1. `[code-verified]` 기존 코드 철학과 정합
  (counter는 event, `/internal/analytics/rule-effectiveness`는 fingerprint).

### D5.2 Prometheus counter만으로 canonical 품질 KPI 정의 금지
- 결정: `fix_confirmation_rate` / `fix_conversion_rate`는 **반드시 Plane B**에서 계산.
  Prometheus에서는 proxy만 표시 가능하며 canonical이 아니다.
- 근거: V4_EVALUATION §3.1, V5 §5.4.

### D5.3 Prometheus ratio는 반드시 window 함수 사용
- 결정: counter ratio는 `sum(counter_a) / sum(counter_b)` 형태 금지.
  `sum(increase(counter_a[window])) / clamp_min(sum(increase(counter_b[window])), 1)` 또는 recording rule.
- 근거: V4_EVALUATION §3.3, V5 §6.2.

### D5.4 `fix_conversion_rate`는 cohort-based
- 결정: "published + resolved" 합계 금지. cohort 정의: "지난 N일에 first-surfaced된 distinct fingerprint"를 분모로, SLA window 내 fixed로 전환된 수를 분자로.
- 근거: V4_EVALUATION §3.2, V5 §6.3.

### D5.5 canonical source는 새 analytics endpoint를 기본으로 한다
- 결정: Plane B의 canonical source는
  `/internal/analytics/finding-outcomes` 새 endpoint를 기본으로 한다.
  materialized rollup / scheduled aggregation은 phase-2 최적화다.
- 근거: V5 §6.4, V5_META_EVALUATION §2.2.5.

### D5.6 Plane B는 immutable lifecycle history를 전제로 한다
- 결정: distinct fingerprint quality KPI를 안정적으로 계산하려면
  publish / suppress / resolved / reopened / feedback command의 시간 이력이 남아야 한다.
  현재 `ThreadSyncState`와 `FindingDecision.state`만으로는 `first_fixed_at`,
  reopen 이후 재해결 여부, 최초 surfaced 시점을 안정적으로 복원할 수 없으므로
  Phase A6는 immutable lifecycle event 저장을 포함한다.
- 근거: `[code-verified]` 현재 모델은 `ThreadSyncState` 최신 상태와
  `FindingDecision` 가변 state만 저장함. `PublicationState`는 publish 이력은 있지만
  resolve/reopen의 immutable history는 없음.

### D5.7 `finding-outcomes` 시점 의미
- 결정:
  - `first_surfaced_at` = 해당 fingerprint의 최초 사용자 가시화 시점
    = `min(PublicationState.published_at)` over successful inline publications.
  - `first_fixed_at` = 해당 fingerprint가 처음 `fixed_in_followup_commit`으로 판정된 lifecycle event 시점.
  - `latest_resolution_reason` = 최신 lifecycle event 기준 resolution reason.
- 이유: `FindingDecision.created_at`은 detect 시점이고,
  cohort KPI의 분모는 실제 사용자에게 surfaced된 시점을 기준으로 해야 한다.

### D5.8 cohort window timezone은 UTC 고정
- 결정: `14d`, `28d` cohort window 경계는 UTC 기준으로 계산한다.
- 이유: 배포 timezone이나 운영자 locale에 따라 KPI가 달라지지 않게 한다.

### D5.9 reopen 이후 재해결은 "첫 fix"만 canonical conversion에 포함
- 결정: `fix_conversion_rate`와 `fix_confirmation_rate`의 canonical 계산은
  첫 surfaced와 첫 fixed를 기준으로 한다.
  reopen/re-fix는 별도 보조 지표(`reopen_rate_*`, `refix_count`)로 관리한다.
- 이유: cohort conversion KPI는 한 finding의 최초 가치 실현 여부를 재는 지표여야 한다.

### D5.10 baseline 기록은 repo 내 versioned snapshot으로 시작한다
- 결정: baseline-v0 / baseline-v1 기록은 초기에는 repo 내 versioned baseline 문서로 남긴다.
  권장 위치는 `docs/baselines/review_bot/`.
  운영이 안정화되면 별도 `analytics_baselines` 저장소로 승격할 수 있다.
- 이유: 초기 도입 비용이 낮고, 문서 기반 의사결정 흐름과 가장 잘 맞는다.

## 6. Metric 계열 / Label (closed)

### D6.1 기존 `findings_*` 계열 rename 금지
- 결정: `findings_published_total` / `findings_resolved_total` / `findings_suppressed_total`을 wholesale rename하지 않는다. label 확장 또는 sibling counter 추가만.
- 근거: V3 §8.1, V4 §8.1.

### D6.2 resolve reason 운영 계측은 sibling counter로 추가한다
- 결정: 현재 `findings_resolved_total{rule_no}`는 유지한다.
  Phase A1/A5에서 sibling counter
  `finding_resolution_events_total{rule_family, resolution_reason}`를 추가한다.
  기존 counter의 label set을 직접 바꾸지 않는다.
- 이유: 기존 metric의 label set을 깨지 않고 cardinality를 `rule_family` 수준으로 낮추며,
  운영 관찰용 resolution event volume만 별도로 확보하기 위함.
- 근거: `[code-verified]` `metrics.py:23-27`, D6.1, V5_META_EVALUATION §2.2.

### D6.3 closed label value sets (V4에서 고정, V5에서 축약되었으나 여기서 복원)
- 결정:
  - `feedback_commands_total{command}`: `command ∈ {ignore, false-positive, later, allow}` (4개만).
  - `verify_attempts_total{mode}` / `verify_dropped_total{mode, reason}`:
    `mode ∈ {llm_self_check, pattern_execution}` (2개로 시작, 확장 시 log 갱신).
  - `verify_dropped_total{reason}`:
    `reason ∈ {not_a_real_bug, low_confidence, pattern_mismatch, execution_error}`.
- 근거: V4 §8.3, V4 §9 A5, V5 §9 A5.

### D6.4 Prometheus label 기본은 `rule_family`, `rule_no` drill-down은 analytics
- 결정: Prometheus label은 `rule_family` 기본. `rule_no` 단위 drill-down은 `/internal/analytics/*` 또는 warehouse.
  cardinality 폭발 방지.
- 근거: V3 §8.3, V4 §8.4.

### D6.5 severity label value migration (Phase A2 완료 후 유효)
- 결정: `findings_published_total`의 `severity` label value를 현재 `low/medium/high`에서 `nitpick|suggestion|warning|critical`로 확장.
  기존 값은 alias.
  **이 migration 전에는 `severity=~"warning|critical"` PromQL이 매치 안 한다. baseline-v0 기간에는 §D6.6 fallback PromQL 사용.**
- 근거: V4 §9 A2, V5 §9 Phase A.

### D6.6 baseline-v0 fallback PromQL (V4에서 박혔고 V5에서 일부 소실되었으나 여기서 복원)
- 결정: label/taxonomy migration 완료 전에는 아래 proxy만 쓴다. canonical이 아님을 본문에 명시.
  - resolve 비율 proxy: `sum(findings_resolved_total) / (sum(findings_published_total) + sum(findings_resolved_total))`
  - high-priority 비중 proxy: `sum(findings_published_total{severity="high"}) / sum(findings_published_total)`
  - suppress 비율: `sum(findings_suppressed_total) / (sum(findings_published_total) + sum(findings_suppressed_total))`
- 근거: V4 §8.5. V5에서 약화된 부분을 복원.

## 7. Existence-Assumption Drift Guard (closed, 메타 규칙)

이 시리즈에서 V2→V3→V4 모두 "아직 존재하지 않는 metric/label/state를 있는 것처럼 쓰는" 부류 실수를 반복했다. 이 실수를 "existence-assumption drift"로 명명하고 다음 라운드에서 예방한다.

**체크리스트: 문서에 아래 요소를 쓰기 전 확인한다.**

- [ ] 새 PromQL → 참조한 counter와 모든 label이 **현재 `metrics.py`에 실제 존재**하는가?
- [ ] 새 `resolution_reason` / `suppression_reason` 값 → 현재 코드에 대입 지점이 있는가? 없다면 "proposed (Phase X)" 주석 필수.
- [ ] 새 endpoint 경로 → 현재 `api/main.py`에 라우트가 있는가? 없다면 "proposed (Phase X)" 주석 필수.
- [ ] 새 DB column / field → 현재 `db/models.py`에 있는가? 없다면 migration 필요 주석 필수.
- [ ] 새 config key (`.review-bot.yaml`) → proposed 여부 주석 필수.

**표기 규칙**: 현재 코드에 없는 것은 문서에서 반드시 `[proposed, Phase X]` 또는 `[after §X migration]` 태그를 붙인다.

## 8. 설정 (closed)

### D8.1 `.review-bot.yaml` 도입은 설정 수렴, 기능 확장 아님
- 결정: `.review-bot.yaml`은 기존 `policy.json + env` 설정 표면을 수렴.
  새 기능(chat, autofix, advanced retrieval)은 스키마 안정화 후 추가.
- 근거: Enhanced §4.2, V4 §9 C3, V5 §9 Phase C.

### D8.2 설정 파일 우선순위
- 결정: `.review-bot.yaml` > `policy.json` > env.
- 근거: V4 §7 P0.4, V5 §8 P0.4.

### D8.3 값 단위 충돌 규칙 = strict override
- 결정: 상위 파일의 명시값이 항상 이긴다.
  예: `.review-bot.yaml`의 `suppressed_rules: [X]`가 `policy.json`의 `allowed_rules: [X]`를 이긴다.
- 근거: V4 §7 P0.4.

### D8.4 단일 파일 내 교차 금지
- 결정: 같은 파일에서 `suppressed_rules ∩ allowed_rules ≠ ∅`이면 **bot error**. silent ambiguity 방지.
- 근거: V4 §7 P0.4, V5 §8 P0.4.

## 9. 로드맵 Phase Naming (closed)

### D9.1 Phase 체계
- 결정: Phase A (Trust) → B (Context) → C (Learning + UX) → D (Automation) 체계를 유지.

### D9.2 Phase A1 naming 이력
- 결정: Phase A1의 의미는 "resolution_reason 확장 + `findings_resolved_total` label 확장" (V3 이후 표준).
  V2 시절 "acceptance tracking 추가"와 동일한 작업을 가리키는 별칭.
- 근거: V2 §5, V3 §9, V4 §9, V3 META §3.2.7.

### D9.3 Phase 간 순서 의존
- 결정: 아래 순서는 엄격히 지킨다. 각 의존을 건너뛰면 상위 작업이 무효.
  - A1 완료 → B / C KPI 계산 가능.
  - A2 완료 → `signal_ratio` PromQL 유효.
  - A5 완료 → verify 관련 운영 지표 유효.
  - A6 완료 → Plane B 품질 KPI canonical 값 확보.
- 근거: V4 §9, V5 §7.

## 10. 외부 벤더 수치 사용 규칙 (closed)

### D10.1 vendor 수치는 KPI 목표로 사용 금지
- 결정: Bugbot 80%, Diamond sub-3%, Greptile 19%→55% 등 vendor self-report는 **방향성 참고치**로만.
  내부 KPI 목표는 반드시 baseline-v1 측정 후 "baseline 대비 개선폭"으로 정의.
- 근거: Evaluation §3.3, Enhanced §3.3, V4 §8.9.

### D10.2 본문 인용 시 태그 필수
- 결정: vendor 수치를 본문에 쓸 때는 `[market-informed]` 태그를 반드시 병기.
- 근거: V4 §2, V5 §1.

## 11. Defer 된 주제 (closed but conditionally)

### D11.1 cross-repo analysis / multi-lang / IDE 실시간 리뷰
- 결정: baseline-v1 확보 전까지 defer. 이 항목들은 acceptance improvement에 대한 기여가 불명확.
- 근거: Enhanced §2.3, V4 §5.7, V5 §9 D.

### D11.2 multi-reviewer 병렬화 (Ellipsis 방식)
- 결정: 폐기가 아닌 **조건부 defer**. D13.1이 충족되면 해제.
- 근거: V2 §5.7, V4 §5.7 / §9 D3.

### D11.3 multi-reviewer 병렬화 해제 조건
- 결정: 두 조건 모두 충족 시만 재평가.
  1. `fix_conversion_rate_28d`가 Phase A/B 이후 2 phase 이상 plateau.
  2. 단일 verify pipeline이 false-positive를 더 못 줄이는 것이 실측됨.
- 근거: V4 §9 D3.

### D11.4 verify phase의 초기 적용 범위
- 결정: verify phase v1은 inline comment publish 후보에만 적용한다.
  walkthrough / ask / summarize 응답에는 초기 적용하지 않는다.
- 근거: V5_META_EVALUATION의 open issue 정리 + 현재 우선순위가 trust foundation에 있음.

## 12. 테스트 / Dev 편의 (closed)

### D12.1 테스트 DB 분리는 해결됨
- 결정: `tests/conftest.py`에서 `PYTEST_XDIST_WORKER + os.getpid()` 기반 worker-scoped SQLite 사용.
  원본의 "공유 SQLite" 지적은 stale. 더 이상 open issue 아님.
- 근거: `[code-verified]` `tests/conftest.py:8-16`. Evaluation §3.2에서 첫 확인.

## 13. 용어 (closed)

- **run summary** ≠ **walkthrough**.
  - run summary = 이번 배치 게시 항목 운영 요약. 현재 `_post_pr_summary`(`review_runner.py:2303`)가 이에 해당.
  - walkthrough = MR onboarding용 설명(변경 요지 / 영향 symbol / 주목 finding). 현재 없음 (Phase C4에서 신설).
- **fingerprint** = unique surfaced finding identity.
- **decision row** = `FindingDecision` 테이블의 단일 record. rerun 시 같은 fingerprint에 복수 row가 쌓일 수 있음.
- **Plane A / Plane B** = 측정 영역 구분 (D5.1).

## 14. 아직 열려 있는 이슈 (open)

현재 이 log 기준으로는 **개발 착수를 막는 open issue는 없다**.
새 쟁점이 생기면 이 섹션에 추가하고,
결정이 닫히면 상위 closed 섹션으로 승격한다.
## 15. 사용 규칙

1. **새 버전 문서를 쓰기 전**에 이 log를 먼저 본다. 중복된 결정을 다시 내리지 않는다.
2. **closed 항목을 바꾸려면** 이 파일의 해당 섹션을 직접 수정하고 근거를 붙인다. 다른 문서에서 변경을 먼저 선언하지 않는다.
3. **§7 existence-assumption drift guard 체크리스트**를 통과하지 않은 PromQL / state / endpoint는 "proposed" 태그 없이 본문에 쓰지 않는다.
4. **§14 open 항목이 결정되면** 해당 항목을 closed 섹션으로 이동한다.
5. **상충하는 결정을 발견하면** 이 log의 결정이 이긴다. 상위 버전 통합본이라도 log와 충돌하면 통합본을 수정.

## 16. 변경 이력

| 날짜 | 변경 | 근거 문서 |
| --- | --- | --- |
| 2026-04-21 | 초기 생성 | `V5_META_EVALUATION.md` §5 (이 log 필요성), `DOCUMENT_FLOW_ASSESSMENT.md` §8 (제안) |
